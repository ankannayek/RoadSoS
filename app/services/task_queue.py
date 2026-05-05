from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.job import BackgroundJob

logger = logging.getLogger(__name__)

JobHandler = Callable[[dict], Awaitable[None]]


class BackgroundTaskQueue:
    """Database-backed queue with in-memory fast path fallback.

    Escalation jobs are persisted in `background_jobs`, so a process restart does
    not permanently drop an active SOS escalation. The lifespan worker polls and
    retries pending/stale jobs.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, JobHandler] = {}
        self._wake_event: asyncio.Event | None = None
        self._stop_event: asyncio.Event | None = None

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def create_task(self, coro: Awaitable, name: str | None = None) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        task.add_done_callback(self._log_result)
        return task

    async def enqueue(
        self,
        db: AsyncSession,
        job_type: str,
        payload: dict,
        max_attempts: int = 3,
        run_at: datetime | None = None,
        dedupe_key: str | None = None,
    ) -> UUID | None:
        if settings.TASK_QUEUE_BACKEND != "database":
            handler = self._handlers.get(job_type)
            if handler:
                self.create_task(handler(payload), name=f"job:{job_type}")
            return None
        if dedupe_key:
            existing = await db.execute(
                select(BackgroundJob.id).where(
                    BackgroundJob.dedupe_key == dedupe_key,
                    BackgroundJob.status.in_(["pending", "running"]),
                )
            )
            existing_id = existing.scalar_one_or_none()
            if existing_id is not None:
                return existing_id
        job = BackgroundJob(
            job_type=job_type,
            dedupe_key=dedupe_key,
            payload_json=payload,
            max_attempts=max_attempts,
            status="pending",
            run_at=run_at or datetime.now(timezone.utc),
        )
        db.add(job)
        await db.flush()
        self.wake()
        return job.id

    async def enqueue_escalation(self, db: AsyncSession, incident_id: str) -> UUID | None:
        return await self.enqueue(
            db,
            "sos_escalation_tier0",
            {"incident_id": str(incident_id)},
            max_attempts=5,
            dedupe_key=f"sos:{incident_id}:tier0",
        )

    async def run_worker_forever(self) -> None:
        if settings.TASK_QUEUE_BACKEND != "database":
            return
        self._wake_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        logger.info("Background task worker started with concurrency=%s", settings.TASK_WORKER_CONCURRENCY)
        workers = [
            asyncio.create_task(self._worker_loop(worker_id), name=f"task-worker:{worker_id}")
            for worker_id in range(max(1, settings.TASK_WORKER_CONCURRENCY))
        ]
        try:
            await self._stop_event.wait()
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        logger.info("Background task worker stopped")

    async def _worker_loop(self, worker_id: int) -> None:
        if self._stop_event is None:
            raise RuntimeError("Task worker stop event was not initialized")
        while not self._stop_event.is_set():
            try:
                worked = await self._run_one_due_job()
                if not worked:
                    try:
                        await asyncio.wait_for(self._wake_event.wait(), timeout=float(settings.TASK_WORKER_POLL_SECONDS))
                    except asyncio.TimeoutError:
                        pass
                    if self._wake_event:
                        self._wake_event.clear()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover
                logger.exception("Background task worker %s loop error: %s", worker_id, exc)
                await asyncio.sleep(2)

    def wake(self) -> None:
        if self._wake_event:
            self._wake_event.set()

    async def stop(self) -> None:
        if self._stop_event:
            self._stop_event.set()
            self.wake()

    async def _run_one_due_job(self) -> bool:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=settings.TASK_LOCK_TIMEOUT_SECONDS)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(BackgroundJob)
                    .where(
                        BackgroundJob.run_at <= now,
                        BackgroundJob.attempts < BackgroundJob.max_attempts,
                        or_(
                            BackgroundJob.status == "pending",
                            (BackgroundJob.status == "running") & (BackgroundJob.locked_at < stale_before),
                        ),
                    )
                    .order_by(BackgroundJob.run_at.asc(), BackgroundJob.created_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                job = result.scalar_one_or_none()
                if job is None:
                    return False
                job.status = "running"
                job.locked_at = now
                job.attempts += 1
                job.error = None
                job_id = job.id
                job_type = job.job_type
                payload = dict(job.payload_json or {})

        handler = self._handlers.get(job_type)
        if not handler:
            await self._mark_failed(job_id, f"No handler registered for {job_type}", retry=False)
            return True

        try:
            await handler(payload)
        except Exception as exc:  # pragma: no cover
            logger.exception("Job %s failed: %s", job_id, exc)
            await self._mark_failed(job_id, str(exc), retry=True)
        else:
            await self._mark_succeeded(job_id)
        return True

    async def _mark_succeeded(self, job_id: UUID) -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(BackgroundJob)
                .where(BackgroundJob.id == job_id)
                .values(status="succeeded", locked_at=None, error=None, updated_at=datetime.now(timezone.utc))
            )
            await db.commit()

    async def _mark_failed(self, job_id: UUID, error: str, retry: bool) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(BackgroundJob).where(BackgroundJob.id == job_id))
            job = result.scalar_one_or_none()
            if job is None:
                return
            if retry and job.attempts < job.max_attempts:
                delay_seconds = min(60 * job.attempts, 300)
                job.status = "pending"
                job.run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            else:
                job.status = "failed"
            job.locked_at = None
            job.error = error[:4000]
            job.updated_at = datetime.now(timezone.utc)
            await db.commit()

    @staticmethod
    def _log_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info("Background task cancelled: %s", task.get_name())
        except Exception as exc:  # pragma: no cover
            logger.exception("Background task failed: %s", exc)


task_queue = BackgroundTaskQueue()

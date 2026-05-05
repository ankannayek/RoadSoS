from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models  # noqa: F401
from app.api import auth, dashboard, data_ingestion, feedback, helper, rag_admin, services, sos, user, volunteer
from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.services import escalation as _escalation  # noqa: F401 - registers durable queue handler
from app.services.db_ping import ping_db_forever
from app.services.rate_limiter import RateLimitMiddleware
from app.services.task_queue import task_queue

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT 1"))
    ping_task = asyncio.create_task(ping_db_forever(), name="db-ping")
    worker_task = asyncio.create_task(task_queue.run_worker_forever(), name="task-worker")
    yield
    await task_queue.stop()
    ping_task.cancel()
    worker_task.cancel()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="Scalable FastAPI backend for RoadSoS: JWT auth, atomic SOS, PostGIS matching, durable escalation, provider notifications, WebSocket status, judge dashboard, feedback re-ranking, data ingestion, and Helper Bot RAG.",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(volunteer.router, prefix="/volunteers", tags=["Volunteers"])
app.include_router(sos.router, prefix="/sos", tags=["SOS"])
app.include_router(helper.router, prefix="/helper", tags=["Helper Bot RAG"])
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
app.include_router(services.router, prefix="/services", tags=["Emergency Services"])
app.include_router(rag_admin.router, prefix="/rag", tags=["RAG Admin"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Judge Dashboard"])
app.include_router(data_ingestion.router, prefix="/data-ingestion", tags=["Multi-source Data Ingestion"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.API_VERSION, "environment": settings.ENVIRONMENT}

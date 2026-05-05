from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import models  # noqa: F401
from app.api import auth, dashboard, data_ingestion, feedback, helper, rag_admin, services, sos, user, volunteer, bundle, relay, voice
from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.services.cache import cache
from app.services import escalation as _escalation  # noqa: F401 - registers durable queue handler
from app.services import overpass as _overpass # noqa: F401 - registers overpass queue handler
from app.services.db_ping import ping_db_forever
from app.services.event_bus import event_bus
from app.services.notifications import notification_hub
from app.services.rate_limiter import RateLimitMiddleware
from app.services.task_queue import task_queue

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_startup_configuration()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT 1"))
    ping_task = asyncio.create_task(ping_db_forever(), name="db-ping")
    worker_task = asyncio.create_task(task_queue.run_worker_forever(), name="task-worker")
    yield
    # Shutdown: close shared httpx client in notification hub.
    await notification_hub.close()
    await task_queue.stop()
    ping_task.cancel()
    worker_task.cancel()
    await asyncio.gather(ping_task, worker_task, return_exceptions=True)
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="Scalable FastAPI backend for RoadSoS: Offline-First Golden Hour Rescue Engine.",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

MAX_BODY_SIZE = 1 * 1024 * 1024  # 1 MB


# ---------------------------------------------------------------------------
# Request-ID middleware — injects a correlation ID into every request/response
# so SOS → escalation → notification log entries can be traced end-to-end.
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    return await call_next(request)


app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Request-ID"],
)


# ---------------------------------------------------------------------------
# Global exception handlers — structured error responses, no stack traces leaked
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)[:200] if exc.body else None},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled error [request_id=%s]: %s", request_id, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(volunteer.router, prefix="/volunteers", tags=["Volunteers"])
app.include_router(sos.router, prefix="/sos", tags=["SOS"])
app.include_router(bundle.router, prefix="/emergency", tags=["Golden Hour Engine"])
app.include_router(relay.router, prefix="/emergency", tags=["Mesh Relay"])
app.include_router(voice.router, prefix="/emergency", tags=["Voice SOS"])
app.include_router(helper.router, prefix="/helper", tags=["Helper Bot RAG"])
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
app.include_router(services.router, prefix="/services", tags=["Emergency Services"])
app.include_router(rag_admin.router, prefix="/rag", tags=["RAG Admin"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Judge Dashboard"])
app.include_router(data_ingestion.router, prefix="/data-ingestion", tags=["Multi-source Data Ingestion"])


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.API_VERSION, "environment": settings.ENVIRONMENT}


@app.get("/health/live")
async def live():
    return {"status": "ok", "version": settings.API_VERSION}


@app.get("/health/ready")
async def ready():
    checks: dict[str, dict[str, object]] = {}

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)[:300]}

    try:
        checks["cache"] = {"ok": await cache.ping()}
    except Exception as exc:
        checks["cache"] = {"ok": False, "error": str(exc)[:300]}

    try:
        checks["event_bus"] = {"ok": await event_bus.ping()}
    except Exception as exc:
        checks["event_bus"] = {"ok": False, "error": str(exc)[:300]}

    checks["queue"] = {"ok": settings.TASK_QUEUE_BACKEND == "database", "backend": settings.TASK_QUEUE_BACKEND}
    fcm_errors = settings.fcm_service_account_errors()
    checks["fcm"] = {
        "ok": (settings.has_fcm_config and not fcm_errors) or not settings.is_production,
        "configured": settings.has_fcm_config,
        "errors": fcm_errors,
    }
    checks["twilio"] = {"ok": settings.has_twilio_config or not settings.is_production, "configured": settings.has_twilio_config}
    checks["field_encryption"] = {"ok": settings.has_field_encryption or not settings.is_production}
    checks["rag_embedding"] = {
        "ok": settings.RAG_EMBEDDING_PROVIDER != "gemini" or bool(settings.GEMINI_API_KEY) or not settings.is_production,
        "provider": settings.RAG_EMBEDDING_PROVIDER,
    }
    checks["rag_llm"] = {
        "ok": (not settings.RAG_LLM_ENABLED)
        or not settings.is_production
        or settings.RAG_LLM_PROVIDER == "extractive"
        or bool(settings.GROQ_API_KEY or settings.GEMINI_API_KEY),
        "provider": settings.RAG_LLM_PROVIDER,
    }

    production_errors = settings.production_config_errors()
    if production_errors:
        checks["production_config"] = {"ok": False, "errors": production_errors}
    else:
        checks["production_config"] = {"ok": True}

    ok = all(bool(check.get("ok")) for check in checks.values())
    payload = {"status": "ready" if ok else "not_ready", "checks": checks}
    if ok:
        return payload
    return JSONResponse(payload, status_code=503)

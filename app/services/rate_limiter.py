from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Request, status
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.services.cache import cache


@dataclass(frozen=True)
class RateLimitPolicy:
    name: str
    requests: int
    window_seconds: int = 60


def policy_for_path(path: str) -> RateLimitPolicy:
    if path.startswith("/auth"):
        return RateLimitPolicy("auth", settings.RATE_LIMIT_AUTH_PER_MINUTE)
    if path.startswith("/sos/trigger"):
        return RateLimitPolicy("sos", settings.RATE_LIMIT_SOS_PER_MINUTE)
    if path.startswith("/helper"):
        return RateLimitPolicy("rag", settings.RATE_LIMIT_RAG_PER_MINUTE)
    return RateLimitPolicy("default", settings.RATE_LIMIT_DEFAULT_PER_MINUTE)


def client_identifier(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        # Token hash avoids storing token itself in cache keys.
        return f"token:{hash(auth[-48:])}"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


class RateLimiter:
    async def hit(self, key: str, policy: RateLimitPolicy) -> tuple[bool, int]:
        bucket_key = f"ratelimit:{policy.name}:{key}:{int(time.time() // policy.window_seconds)}"
        current = await cache.get(bucket_key)
        count = int(current or 0) + 1
        await cache.set(bucket_key, count, ttl_seconds=policy.window_seconds + 2)
        remaining = max(policy.requests - count, 0)
        return count <= policy.requests, remaining


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"} or request.url.path.startswith("/ws/"):
            return await call_next(request)
        policy = policy_for_path(request.url.path)
        ok, remaining = await rate_limiter.hit(client_identifier(request), policy)
        if not ok:
            return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": f"Rate limit exceeded for {policy.name}. Try again shortly."})
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(policy.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

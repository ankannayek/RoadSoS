from __future__ import annotations

import hashlib
import ipaddress
import time
from dataclasses import dataclass

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
    if path.startswith("/emergency/mesh-relay"):
        return RateLimitPolicy("relay", settings.RATE_LIMIT_RELAY_PER_MINUTE)
    if path.startswith("/emergency/voice"):
        return RateLimitPolicy("voice", settings.RATE_LIMIT_VOICE_PER_MINUTE)
    if path.startswith("/helper"):
        return RateLimitPolicy("rag", settings.RATE_LIMIT_RAG_PER_MINUTE)
    return RateLimitPolicy("default", settings.RATE_LIMIT_DEFAULT_PER_MINUTE)


def client_identifier(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        digest = hashlib.sha256(auth.removeprefix("Bearer ").removeprefix("bearer ").encode("utf-8")).hexdigest()
        return f"token:{digest}"
    forwarded = request.headers.get("x-forwarded-for") if settings.TRUST_PROXY_HEADERS else None
    if forwarded:
        raw_ip = forwarded.split(",")[0].strip()
        try:
            normalized = str(ipaddress.ip_address(raw_ip))
        except ValueError:
            normalized = "invalid-forwarded-ip"
        return f"ip:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"
    host = request.client.host if request.client else "unknown"
    try:
        host = str(ipaddress.ip_address(host))
    except ValueError:
        host = "unknown"
    return f"ip:{hashlib.sha256(host.encode('utf-8')).hexdigest()}"


class RateLimiter:
    async def hit(self, key: str, policy: RateLimitPolicy) -> tuple[bool, int]:
        bucket_key = f"ratelimit:{policy.name}:{key}:{int(time.time() // policy.window_seconds)}"
        count = await cache.increment_window(bucket_key, ttl_seconds=policy.window_seconds + 2)
        remaining = max(policy.requests - count, 0)
        return count <= policy.requests, remaining


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/health") or path in {"/docs", "/openapi.json", "/redoc"} or "/ws" in path:
            return await call_next(request)
        policy = policy_for_path(request.url.path)
        ok, remaining = await rate_limiter.hit(client_identifier(request), policy)
        if not ok:
            return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": f"Rate limit exceeded for {policy.name}. Try again shortly."})
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(policy.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

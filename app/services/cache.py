from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from app.core.config import settings

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover - optional dependency in local dev
    redis = None


class Cache:
    async def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def increment_window(self, key: str, ttl_seconds: int) -> int:
        raise NotImplementedError

    async def ping(self) -> bool:
        raise NotImplementedError


class RedisCache(Cache):
    def __init__(self, url: str) -> None:
        if redis is None:
            raise RuntimeError("redis package is not installed")
        self.client = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        raw = await self.client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        await self.client.set(key, json.dumps(value, default=str), ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def increment_window(self, key: str, ttl_seconds: int) -> int:
        script = """
        local current = redis.call('INCR', KEYS[1])
        if current == 1 then
            redis.call('EXPIRE', KEYS[1], ARGV[1])
        end
        return current
        """
        return int(await self.client.eval(script, 1, key, int(ttl_seconds)))

    async def ping(self) -> bool:
        return bool(await self.client.ping())

class InMemoryCache(Cache):
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < time.time():
                self._data.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        async with self._lock:
            self._data[key] = (time.time() + ttl_seconds, value)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def increment_window(self, key: str, ttl_seconds: int) -> int:
        async with self._lock:
            expires_at, value = self._data.get(key, (time.time() + ttl_seconds, 0))
            if expires_at < time.time():
                expires_at, value = time.time() + ttl_seconds, 0
            value = int(value) + 1
            self._data[key] = (expires_at, value)
            return value

    async def ping(self) -> bool:
        return True

def build_cache() -> Cache:
    if settings.REDIS_URL:
        try:
            return RedisCache(settings.REDIS_URL)
        except Exception as exc:
            if settings.is_production and settings.REQUIRE_REDIS_IN_PRODUCTION:
                raise RuntimeError("Redis cache is required in production") from exc
            return InMemoryCache()
    if settings.is_production and settings.REQUIRE_REDIS_IN_PRODUCTION:
        raise RuntimeError("REDIS_URL is required in production when REQUIRE_REDIS_IN_PRODUCTION=true")
    return InMemoryCache()


cache = build_cache()

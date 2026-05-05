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


def build_cache() -> Cache:
    if settings.REDIS_URL:
        try:
            return RedisCache(settings.REDIS_URL)
        except Exception:
            # Local fallback lets development continue; production should alert.
            return InMemoryCache()
    return InMemoryCache()


cache = build_cache()

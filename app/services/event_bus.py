from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, AsyncIterator, Dict, List

from app.core.config import settings

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None


class EventBus:
    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        raise NotImplementedError

    async def subscribe(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(channel, []))
        for queue in queues:
            await queue.put(event)

    async def subscribe(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[channel].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                if queue in self._subscribers.get(channel, []):
                    self._subscribers[channel].remove(queue)


class RedisEventBus(EventBus):
    def __init__(self, url: str) -> None:
        if redis is None:
            raise RuntimeError("redis package not installed")
        self.client = redis.from_url(url, decode_responses=True)

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        await self.client.publish(channel, json.dumps(event, default=str))

    async def subscribe(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()


def build_event_bus() -> EventBus:
    if settings.REDIS_URL:
        try:
            return RedisEventBus(settings.REDIS_URL)
        except Exception as exc:
            if settings.is_production and settings.REQUIRE_REDIS_IN_PRODUCTION:
                raise RuntimeError("Redis Pub/Sub is required in production") from exc
            return InMemoryEventBus()
    if settings.is_production and settings.REQUIRE_REDIS_IN_PRODUCTION:
        raise RuntimeError("REDIS_URL is required in production when REQUIRE_REDIS_IN_PRODUCTION=true")
    return InMemoryEventBus()


event_bus = build_event_bus()

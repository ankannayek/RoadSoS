from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict

from app.core.config import settings

logger = logging.getLogger(__name__)


class EventBus:
    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        raise NotImplementedError

    async def subscribe(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        raise NotImplementedError

class InMemoryEventBus(EventBus):
    """Development-only in-process event bus.

    WARNING: In a multi-worker deployment, events published in one worker
    are INVISIBLE to subscribers in other workers. Use RedisEventBus in
    production for cross-worker event delivery.
    """

    def __init__(self) -> None:
        self._channels: Dict[str, list[asyncio.Queue[Dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        async with self._lock:
            queues = self._channels.get(channel, [])
            dead_queues: list[asyncio.Queue] = []
            for queue in queues:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Drop oldest event to prevent unbounded memory growth.
                    try:
                        queue.get_nowait()
                        queue.put_nowait(event)
                    except (asyncio.QueueEmpty, asyncio.QueueFull):
                        dead_queues.append(queue)
            # Clean up dead queues.
            if dead_queues:
                self._channels[channel] = [q for q in queues if q not in dead_queues]

    async def subscribe(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._channels.setdefault(channel, []).append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            async with self._lock:
                queues = self._channels.get(channel, [])
                if queue in queues:
                    queues.remove(queue)
                if not queues:
                    self._channels.pop(channel, None)

    async def ping(self) -> bool:
        return True

    @property
    def subscriber_count(self) -> int:
        """Total active subscriber queues across all channels."""
        return sum(len(queues) for queues in self._channels.values())


class RedisEventBus:
    """Production pub/sub event bus backed by Redis.

    Guarantees cross-worker event delivery for WebSocket streaming.
    Uses Redis Pub/Sub so that an incident event published by the
    escalation worker is received by all WebSocket-serving workers.
    """

    def __init__(self) -> None:
        self._redis = None
        self._pubsub_connections: list[Any] = []
        self._lock = asyncio.Lock()

    def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=20,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
        return self._redis

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        try:
            r = self._get_redis()
            await r.publish(channel, json.dumps(event, default=str))
        except Exception as exc:
            logger.error("Redis publish to %s failed: %s", channel, exc)

    async def subscribe(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        r = self._get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        async with self._lock:
            self._pubsub_connections.append(pubsub)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        yield json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        continue
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            async with self._lock:
                if pubsub in self._pubsub_connections:
                    self._pubsub_connections.remove(pubsub)

    async def ping(self) -> bool:
        try:
            r = self._get_redis()
            return await r.ping()
        except Exception:
            return False

    @property
    def subscriber_count(self) -> int:
        return len(self._pubsub_connections)


def build_event_bus() -> InMemoryEventBus | RedisEventBus:
    """Select event bus backend based on config.

    Redis is required in production for cross-worker WebSocket delivery.
    InMemory is acceptable for single-worker local development only.
    """
    if settings.REDIS_URL:
        try:
            bus = RedisEventBus()
            logger.info("Event bus: Redis (production mode)")
            return bus
        except Exception as exc:
            if settings.is_production and settings.REQUIRE_REDIS_IN_PRODUCTION:
                raise RuntimeError("Redis event bus required in production but failed to initialize") from exc
            logger.warning("Redis event bus init failed; falling back to InMemory: %s", exc)

    if settings.is_production and settings.REQUIRE_REDIS_IN_PRODUCTION:
        raise RuntimeError("Redis event bus required in production (REQUIRE_REDIS_IN_PRODUCTION=true)")
    logger.info("Event bus: InMemory (development mode)")
    return InMemoryEventBus()


event_bus = build_event_bus()

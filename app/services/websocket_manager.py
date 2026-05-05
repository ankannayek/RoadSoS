from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Dict

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)

# Maximum concurrent WebSocket connections per stream type.
MAX_INCIDENT_SUBSCRIBERS = 500
MAX_DASHBOARD_SUBSCRIBERS = 50
HEARTBEAT_INTERVAL_SECONDS = 30


class WebSocketManager:
    """Manages WebSocket streams for incident tracking and dashboard.

    Production improvements:
    - Connection limits to prevent memory exhaustion.
    - Heartbeat pings to detect dead connections.
    - Proper cleanup on disconnect (no leaked subscriber queues).
    """

    def __init__(self) -> None:
        self._incident_connections: int = 0
        self._dashboard_connections: int = 0

    async def _send_heartbeats(self, websocket: WebSocket) -> None:
        """Periodically send lightweight heartbeats to detect dead clients."""
        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception as exc:
                    logger.debug("WebSocket heartbeat failed: %s", exc)
                    break
        except asyncio.CancelledError:
            return

    async def stream_incident(self, websocket: WebSocket, incident_id: str) -> None:
        if self._incident_connections >= MAX_INCIDENT_SUBSCRIBERS:
            await websocket.close(code=1013, reason="Too many connections")
            return

        await websocket.accept()
        self._incident_connections += 1
        heartbeat_task = asyncio.create_task(self._send_heartbeats(websocket))
        try:
            await websocket.send_json({"type": "connected", "stream": "incident", "incident_id": incident_id})
            async for event in event_bus.subscribe(f"incident:{incident_id}"):
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                await websocket.send_json(event)
        except Exception as exc:
            logger.warning("Incident WebSocket stream failed for %s: %s", incident_id, exc)
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task
            self._incident_connections = max(0, self._incident_connections - 1)

    async def stream_dashboard(self, websocket: WebSocket) -> None:
        if self._dashboard_connections >= MAX_DASHBOARD_SUBSCRIBERS:
            await websocket.close(code=1013, reason="Too many dashboard connections")
            return

        await websocket.accept()
        self._dashboard_connections += 1
        heartbeat_task = asyncio.create_task(self._send_heartbeats(websocket))
        try:
            await websocket.send_json({"type": "connected", "stream": "dashboard"})
            async for event in event_bus.subscribe("dashboard:incidents"):
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                await websocket.send_json(event)
        except Exception as exc:
            logger.warning("Dashboard WebSocket stream failed: %s", exc)
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task
            self._dashboard_connections = max(0, self._dashboard_connections - 1)

    async def publish_incident_event(self, incident_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"type": event_type, "incident_id": incident_id, "payload": payload}
        await event_bus.publish(f"incident:{incident_id}", event)

    async def publish_dashboard_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        await event_bus.publish("dashboard:incidents", {"type": event_type, "payload": payload})

    @property
    def active_connections(self) -> Dict[str, int]:
        return {
            "incident": self._incident_connections,
            "dashboard": self._dashboard_connections,
        }


websocket_manager = WebSocketManager()

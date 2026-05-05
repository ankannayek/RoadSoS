from __future__ import annotations

from typing import Any, Dict

from fastapi import WebSocket

from app.services.event_bus import event_bus


class WebSocketManager:
    async def stream_incident(self, websocket: WebSocket, incident_id: str) -> None:
        await websocket.accept()
        await websocket.send_json({"type": "connected", "stream": "incident", "incident_id": incident_id})
        async for event in event_bus.subscribe(f"incident:{incident_id}"):
            await websocket.send_json(event)

    async def stream_dashboard(self, websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"type": "connected", "stream": "dashboard"})
        async for event in event_bus.subscribe("dashboard:incidents"):
            await websocket.send_json(event)

    async def publish_incident_event(self, incident_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"type": event_type, "incident_id": incident_id, "payload": payload}
        await event_bus.publish(f"incident:{incident_id}", event)

    async def publish_dashboard_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        await event_bus.publish("dashboard:incidents", {"type": event_type, "payload": payload})


websocket_manager = WebSocketManager()

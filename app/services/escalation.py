from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select, update

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.incident import Incident, IncidentStatus
from app.models.user import User
from app.services.geo import find_nearby_services, find_nearby_volunteers
from app.services.notifications import notification_hub
from app.services.task_queue import task_queue
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


def _delay(seconds: int) -> int:
    if settings.ESCALATION_DEMO_MODE:
        return max(2, min(10, seconds // 30))
    return seconds


async def _incident_active(db, incident_id: UUID) -> bool:
    result = await db.execute(select(Incident.status).where(Incident.id == incident_id))
    current_status = result.scalar_one_or_none()
    return current_status in {IncidentStatus.ACTIVE, IncidentStatus.ESCALATED, IncidentStatus.ACKNOWLEDGED}


async def _mark_escalated(db, incident_id: UUID) -> None:
    await db.execute(update(Incident).where(Incident.id == incident_id).values(status=IncidentStatus.ESCALATED))
    await db.commit()


def _incident_payload(incident: Incident, tier: str) -> Dict[str, Any]:
    return {
        "incident_id": str(incident.id),
        "tier": tier,
        "priority": incident.priority.value if hasattr(incident.priority, "value") else str(incident.priority),
        "lat": incident.lat,
        "lng": incident.lng,
        "silent": incident.silent,
        "source": incident.source.value if hasattr(incident.source, "value") else str(incident.source),
        "description": incident.description[:300],
    }


async def start_escalation_ladder(incident_id: str) -> None:
    """Heuristic-only escalation ladder.

    No AI/RAG is used here. SOS routing is deterministic:
    - Tier 0 immediately notifies nearby volunteers and emergency contacts.
    - Tier 1 after 90s escalates official services for P1/P2.
    - Tier 2 after 180s widens radius and pushes dashboard/SMS fallback.
    - Tier 3 keeps rebroadcasting until resolved/cancelled.
    """
    incident_uuid = UUID(str(incident_id))
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Incident).where(Incident.id == incident_uuid))
        incident = result.scalar_one_or_none()
        if incident is None:
            logger.warning("Escalation requested for missing incident %s", incident_id)
            return
        user = await db.get(User, incident.user_id)
        contacts = (user.emergency_contacts or []) if user else []

        volunteers = await find_nearby_volunteers(incident.lat, incident.lng, db=db)
        payload = _incident_payload(incident, "tier0")
        volunteer_count = await notification_hub.notify_volunteers(db, incident_id, volunteers, payload)
        contact_count = await notification_hub.notify_contacts(db, incident_id, contacts, payload)
        await db.commit()
        await websocket_manager.publish_incident_event(
            incident_id,
            "tier0_dispatched",
            {"volunteers": volunteer_count, "contacts": contact_count, "services": 0},
        )
        await websocket_manager.publish_dashboard_event("incident_dispatched", {"incident_id": incident_id, "tier": "tier0"})

    await asyncio.sleep(_delay(settings.ESCALATION_TIER1_SECONDS))
    async with AsyncSessionLocal() as db:
        if not await _incident_active(db, incident_uuid):
            return
        result = await db.execute(select(Incident).where(Incident.id == incident_uuid))
        incident = result.scalar_one()
        priority = incident.priority.value if hasattr(incident.priority, "value") else str(incident.priority)
        if priority in {"P1_CRITICAL", "P2_HIGH"}:
            services = await find_nearby_services(
                incident.lat,
                incident.lng,
                db=db,
                types=["AMBULANCE", "TRAUMA", "HOSPITAL", "POLICE", "FIRE"],
                limit=10,
            )
            await notification_hub.notify_services(db, incident_id, services, _incident_payload(incident, "tier1"))
            await _mark_escalated(db, incident_uuid)
            await websocket_manager.publish_incident_event(incident_id, "tier1_escalated", {"services": len(services)})
            await websocket_manager.publish_dashboard_event("incident_escalated", {"incident_id": incident_id, "tier": "tier1", "services": len(services)})

    await asyncio.sleep(_delay(settings.ESCALATION_TIER2_SECONDS - settings.ESCALATION_TIER1_SECONDS))
    async with AsyncSessionLocal() as db:
        if not await _incident_active(db, incident_uuid):
            return
        result = await db.execute(select(Incident).where(Incident.id == incident_uuid))
        incident = result.scalar_one()
        volunteers = await find_nearby_volunteers(incident.lat, incident.lng, db=db, radius_km=25, limit=20)
        services = await find_nearby_services(incident.lat, incident.lng, db=db, radius_km=50, limit=20)
        await notification_hub.notify_volunteers(db, incident_id, volunteers, _incident_payload(incident, "tier2"))
        await notification_hub.notify_services(db, incident_id, services, _incident_payload(incident, "tier2"))
        await db.commit()
        await websocket_manager.publish_incident_event(incident_id, "tier2_broadcast", {"volunteers": len(volunteers), "services": len(services)})
        await websocket_manager.publish_dashboard_event("incident_broadcast", {"incident_id": incident_id, "tier": "tier2", "volunteers": len(volunteers), "services": len(services)})

    await asyncio.sleep(_delay(settings.ESCALATION_TIER3_SECONDS - settings.ESCALATION_TIER2_SECONDS))
    repeat_seconds = _delay(settings.ESCALATION_TIER1_SECONDS)
    while True:
        async with AsyncSessionLocal() as db:
            if not await _incident_active(db, incident_uuid):
                return
            result = await db.execute(select(Incident).where(Incident.id == incident_uuid))
            incident = result.scalar_one()
            volunteers = await find_nearby_volunteers(incident.lat, incident.lng, db=db, radius_km=50, limit=30)
            services = await find_nearby_services(incident.lat, incident.lng, db=db, radius_km=50, limit=25)
            await notification_hub.notify_volunteers(db, incident_id, volunteers, _incident_payload(incident, "tier3"))
            await notification_hub.notify_services(db, incident_id, services, _incident_payload(incident, "tier3"))
            await db.commit()
            await websocket_manager.publish_incident_event(
                incident_id,
                "tier3_dashboard_alert",
                {"message": "Incident still active; dashboard verification required.", "volunteers": len(volunteers), "services": len(services)},
            )
            await websocket_manager.publish_dashboard_event(
                "incident_tier3_rebroadcast",
                {"incident_id": incident_id, "tier": "tier3", "volunteers": len(volunteers), "services": len(services)},
            )
        await asyncio.sleep(repeat_seconds)


async def handle_sos_escalation_job(payload: dict) -> None:
    incident_id = payload.get("incident_id")
    if not incident_id:
        raise ValueError("Missing incident_id")
    await start_escalation_ladder(str(incident_id))


task_queue.register("sos_escalation", handle_sos_escalation_job)

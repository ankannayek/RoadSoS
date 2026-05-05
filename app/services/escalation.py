from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.incident import Incident, IncidentStatus
from app.models.user import User
from app.services.geo import find_nearby_services, find_nearby_volunteers
from app.services.notifications import notification_hub
from app.services.private_profile import load_private_profile
from app.services.task_queue import task_queue
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


def _delay(seconds: int) -> int:
    if settings.ESCALATION_DEMO_MODE:
        return max(2, min(10, seconds // 30))
    return seconds


def _run_at_after(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=_delay(seconds))


async def _incident_active(db: AsyncSession, incident_id: UUID) -> bool:
    result = await db.execute(select(Incident.status).where(Incident.id == incident_id))
    current_status = result.scalar_one_or_none()
    return current_status in {IncidentStatus.ACTIVE, IncidentStatus.ESCALATED, IncidentStatus.ACKNOWLEDGED}


async def _mark_escalated(db: AsyncSession, incident_id: UUID) -> None:
    await db.execute(update(Incident).where(Incident.id == incident_id).values(status=IncidentStatus.ESCALATED))


def _incident_payload(incident: Incident, tier: str) -> Dict[str, Any]:
    return {
        "incident_id": str(incident.id),
        "tier": tier,
        "priority": incident.priority.value if hasattr(incident.priority, "value") else str(incident.priority),
        "lat": incident.lat,
        "lng": incident.lng,
        "silent": incident.silent,
        "bystander_mode": incident.bystander_mode,
        "source": incident.source.value if hasattr(incident.source, "value") else str(incident.source),
        "description": incident.description[:300],
    }


async def _get_incident(db: AsyncSession, incident_id: str) -> Incident | None:
    incident_uuid = UUID(str(incident_id))
    result = await db.execute(select(Incident).where(Incident.id == incident_uuid))
    return result.scalar_one_or_none()


async def _schedule_tier(db: AsyncSession, incident_id: str, tier: str, delay_seconds: int) -> None:
    await task_queue.enqueue(
        db,
        f"sos_escalation_{tier}",
        {"incident_id": incident_id},
        max_attempts=5,
        run_at=_run_at_after(delay_seconds),
        dedupe_key=f"sos:{incident_id}:{tier}",
    )


async def handle_tier0(payload: dict) -> None:
    """Immediate first response for a new SOS incident."""
    incident_id = str(payload.get("incident_id") or "")
    if not incident_id:
        raise ValueError("Missing incident_id")

    async with AsyncSessionLocal() as db:
        incident = await _get_incident(db, incident_id)
        if incident is None:
            logger.warning("Tier0 requested for missing incident %s", incident_id)
            return
        if not await _incident_active(db, incident.id):
            return

        user = await db.get(User, incident.user_id)
        private_profile = await load_private_profile(db, user) if user else {"emergency_contacts": []}
        contacts = private_profile.get("emergency_contacts") or []

        volunteers = await find_nearby_volunteers(incident.lat, incident.lng, db=db)
        event_payload = _incident_payload(incident, "tier0")
        volunteer_count = await notification_hub.notify_volunteers(db, incident_id, volunteers, event_payload)
        contact_count = await notification_hub.notify_contacts(db, incident_id, contacts, event_payload)

        services_notified = 0
        priority = incident.priority.value if hasattr(incident.priority, "value") else str(incident.priority)
        if priority == "P1_CRITICAL":
            services = await find_nearby_services(
                incident.lat,
                incident.lng,
                db=db,
                types=["AMBULANCE", "TRAUMA", "HOSPITAL", "POLICE", "FIRE"],
                limit=10,
            )
            services_notified = await notification_hub.notify_services(db, incident_id, services, event_payload)
            await _mark_escalated(db, incident.id)

        await _schedule_tier(db, incident_id, "tier1", settings.ESCALATION_TIER1_SECONDS)
        await db.commit()

    await websocket_manager.publish_incident_event(
        incident_id,
        "tier0_dispatched",
        {"volunteers": volunteer_count, "contacts": contact_count, "services": services_notified},
    )
    await websocket_manager.publish_dashboard_event(
        "incident_dispatched",
        {
            "incident_id": incident_id,
            "tier": "tier0",
            "priority": priority,
            "services_immediate": services_notified,
        },
    )


async def handle_legacy_escalation(payload: dict) -> None:
    await handle_tier0(payload)


async def handle_tier1(payload: dict) -> None:
    """Escalate to official services for unresolved P1/P2 incidents."""
    incident_id = str(payload.get("incident_id") or "")
    if not incident_id:
        raise ValueError("Missing incident_id")

    async with AsyncSessionLocal() as db:
        incident = await _get_incident(db, incident_id)
        if incident is None or not await _incident_active(db, incident.id):
            return

        priority = incident.priority.value if hasattr(incident.priority, "value") else str(incident.priority)
        services_notified = 0
        if priority in {"P1_CRITICAL", "P2_HIGH"}:
            services = await find_nearby_services(
                incident.lat,
                incident.lng,
                db=db,
                types=["AMBULANCE", "TRAUMA", "HOSPITAL", "POLICE", "FIRE"],
                limit=10,
                radius_km=30,
            )
            services_notified = await notification_hub.notify_services(db, incident_id, services, _incident_payload(incident, "tier1"))
            await _mark_escalated(db, incident.id)

        await _schedule_tier(db, incident_id, "tier2", settings.ESCALATION_TIER2_SECONDS - settings.ESCALATION_TIER1_SECONDS)
        await db.commit()

    if services_notified:
        await websocket_manager.publish_incident_event(incident_id, "tier1_escalated", {"services": services_notified})
        await websocket_manager.publish_dashboard_event(
            "incident_escalated",
            {"incident_id": incident_id, "tier": "tier1", "services": services_notified},
        )


async def handle_tier2(payload: dict) -> None:
    incident_id = str(payload.get("incident_id") or "")
    if not incident_id:
        raise ValueError("Missing incident_id")

    async with AsyncSessionLocal() as db:
        incident = await _get_incident(db, incident_id)
        if incident is None or not await _incident_active(db, incident.id):
            return

        volunteers = await find_nearby_volunteers(incident.lat, incident.lng, db=db, radius_km=25, limit=20)
        services = await find_nearby_services(incident.lat, incident.lng, db=db, radius_km=50, limit=20)
        event_payload = _incident_payload(incident, "tier2")
        volunteer_count = await notification_hub.notify_volunteers(db, incident_id, volunteers, event_payload)
        service_count = await notification_hub.notify_services(db, incident_id, services, event_payload)
        await _schedule_tier(db, incident_id, "tier3", settings.ESCALATION_TIER3_SECONDS - settings.ESCALATION_TIER2_SECONDS)
        await db.commit()

    await websocket_manager.publish_incident_event(incident_id, "tier2_broadcast", {"volunteers": volunteer_count, "services": service_count})
    await websocket_manager.publish_dashboard_event(
        "incident_broadcast",
        {"incident_id": incident_id, "tier": "tier2", "volunteers": volunteer_count, "services": service_count},
    )


async def handle_tier3(payload: dict) -> None:
    incident_id = str(payload.get("incident_id") or "")
    if not incident_id:
        raise ValueError("Missing incident_id")

    async with AsyncSessionLocal() as db:
        incident = await _get_incident(db, incident_id)
        if incident is None or not await _incident_active(db, incident.id):
            return

        volunteers = await find_nearby_volunteers(incident.lat, incident.lng, db=db, radius_km=50, limit=30)
        services = await find_nearby_services(incident.lat, incident.lng, db=db, radius_km=50, limit=25)
        event_payload = _incident_payload(incident, "tier3")
        volunteer_count = await notification_hub.notify_volunteers(db, incident_id, volunteers, event_payload)
        service_count = await notification_hub.notify_services(db, incident_id, services, event_payload)
        await task_queue.enqueue(
            db,
            "sos_escalation_tier3",
            {"incident_id": incident_id},
            max_attempts=5,
            run_at=_run_at_after(settings.ESCALATION_TIER1_SECONDS),
            dedupe_key=f"sos:{incident_id}:tier3:{int(datetime.now(timezone.utc).timestamp() // max(_delay(settings.ESCALATION_TIER1_SECONDS), 1))}",
        )
        await db.commit()

    await websocket_manager.publish_incident_event(
        incident_id,
        "tier3_dashboard_alert",
        {
            "message": "Incident still active; dashboard verification required.",
            "volunteers": volunteer_count,
            "services": service_count,
        },
    )
    await websocket_manager.publish_dashboard_event(
        "incident_tier3_rebroadcast",
        {"incident_id": incident_id, "tier": "tier3", "volunteers": volunteer_count, "services": service_count},
    )


task_queue.register("sos_escalation_tier0", handle_tier0)
task_queue.register("sos_escalation", handle_legacy_escalation)
task_queue.register("sos_escalation_tier1", handle_tier1)
task_queue.register("sos_escalation_tier2", handle_tier2)
task_queue.register("sos_escalation_tier3", handle_tier3)

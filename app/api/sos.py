from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import authenticate_websocket_user, get_current_user
from app.db.session import AsyncSessionLocal, get_db
from app.models.incident import Incident, IncidentSource, IncidentStatus, PriorityEnum
from app.models.user import User
from app.schemas.sos import IncidentOut, IncidentStatusUpdate, LiveLocationUpdate, OfflineServicesResponse, SMSFallbackPayload, SOSResponse, SOSTrigger
from app.services.classifier import classify_emergency, response_eta
from app.services.geo import get_offline_services_prefetch
<<<<<<< HEAD
from app.services.private_profile import load_private_profile
=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
from app.services.task_queue import task_queue
from app.services.websocket_manager import websocket_manager

router = APIRouter()


async def _owned_incident(db: AsyncSession, incident_id: UUID, user: User) -> Incident:
<<<<<<< HEAD
    if user.role in {"dispatcher", "judge", "admin"}:
        result = await db.execute(select(Incident).where(Incident.id == incident_id))
    else:
        result = await db.execute(select(Incident).where(Incident.id == incident_id, Incident.user_id == user.id))
=======
    result = await db.execute(select(Incident).where(Incident.id == incident_id, Incident.user_id == user.id))
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/trigger", response_model=SOSResponse, status_code=status.HTTP_200_OK)
async def trigger_sos(payload: SOSTrigger, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Atomic SOS handler.

    Fast path: validate JWT + deterministic triage + one DB transaction + HTTP 200.
    Slow path: geo matching, notifications, and escalation run from the durable job queue.
    """
<<<<<<< HEAD
    priority_label, confidence = classify_emergency(payload.description, payload.impact_force or 0, payload.sensor_payload, source=payload.source)
=======
    priority_label, confidence = classify_emergency(payload.description, payload.impact_force or 0, payload.sensor_payload)
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    incident = Incident(
        user_id=current_user.id,
        description=payload.description,
        priority=PriorityEnum(priority_label),
        triage_confidence=confidence,
        source=IncidentSource(payload.source),
        silent=payload.silent or payload.source == "silent",
        bystander_mode=payload.bystander_mode or payload.source == "bystander",
        victim_name=payload.victim_name,
        victim_phone=payload.victim_phone,
        lat=payload.lat,
        lng=payload.lng,
        status=IncidentStatus.ACTIVE,
        metadata_json={"sensor_payload": payload.sensor_payload},
    )
    db.add(incident)
    await db.flush()
    await task_queue.enqueue_escalation(db, str(incident.id))
    await db.commit()
    await db.refresh(incident)

    await websocket_manager.publish_incident_event(str(incident.id), "created", {"priority": priority_label, "lat": payload.lat, "lng": payload.lng})
    await websocket_manager.publish_dashboard_event("incident_created", {"incident_id": str(incident.id), "priority": priority_label, "lat": payload.lat, "lng": payload.lng})

<<<<<<< HEAD
    # Bystander mode safety warning.
    message = "SOS received. Help dispatch has started."
    is_bystander = payload.bystander_mode or payload.source == "bystander"
    if is_bystander and not payload.victim_name:
        message = (
            "SOS received in bystander mode. Help dispatch has started. "
            "TIP: Providing the victim's name and phone (if known) helps "
            "responders reach and identify them faster."
        )

=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    return SOSResponse(
        incident_id=incident.id,
        priority=priority_label,
        triage_confidence=confidence,
        estimated_response_time=response_eta(priority_label),
<<<<<<< HEAD
        message=message,
=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    )


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
async def get_incident(incident_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await _owned_incident(db, incident_id, current_user)


@router.patch("/incidents/{incident_id}/status", response_model=IncidentOut)
async def update_incident_status(incident_id: UUID, payload: IncidentStatusUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    incident = await _owned_incident(db, incident_id, current_user)
    incident.status = IncidentStatus(payload.status)
    if payload.status in {"resolved", "cancelled"}:
        incident.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(incident)
    await websocket_manager.publish_incident_event(str(incident.id), "status_updated", {"status": payload.status, "note": payload.note})
    await websocket_manager.publish_dashboard_event("incident_status_updated", {"incident_id": str(incident.id), "status": payload.status})
    return incident


@router.post("/incidents/{incident_id}/location")
async def update_live_location(incident_id: UUID, payload: LiveLocationUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if payload.incident_id != incident_id:
        raise HTTPException(status_code=400, detail="Incident id mismatch")
    await _owned_incident(db, incident_id, current_user)
    await websocket_manager.publish_incident_event(str(incident_id), "location_updated", payload.model_dump(mode="json"))
    await websocket_manager.publish_dashboard_event("incident_location_updated", {"incident_id": str(incident_id), "lat": payload.lat, "lng": payload.lng})
    return {"status": "ok"}


@router.get("/offline-services", response_model=OfflineServicesResponse)
async def offline_services(lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_offline_services_prefetch(lat, lng, db=db)


@router.get("/sms-fallback-payload", response_model=SMSFallbackPayload)
async def sms_fallback_payload(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offline = await get_offline_services_prefetch(lat, lng, db=db)
    numbers = [settings.SMS_FALLBACK_NUMBER]
    for service in offline.get("services", []):
        phone = service.get("phone")
        if phone and phone not in numbers:
            numbers.append(phone)
    maps_url = f"https://maps.google.com/?q={lat},{lng}"
<<<<<<< HEAD
    private_profile = await load_private_profile(db, current_user)
    medical = ", ".join(
        part
        for part in [
            private_profile.get("blood_group"),
            private_profile.get("medical_conditions"),
            private_profile.get("allergies"),
        ]
        if part
    )
=======
    medical = ", ".join(part for part in [current_user.blood_group, current_user.medical_conditions, current_user.allergies] if part)
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    message = f"RoadSoS OFFLINE SOS. Need help at {maps_url}. User: {current_user.name}, phone {current_user.phone}. Medical: {medical or 'not provided'}."
    return SMSFallbackPayload(sms_to=numbers[:5], message=message[:480], lat=lat, lng=lng, maps_url=maps_url)


@router.websocket("/ws/{incident_id}")
async def incident_websocket(websocket: WebSocket, incident_id: str):
    try:
        async with AsyncSessionLocal() as db:
            user = await authenticate_websocket_user(websocket, db)
            result = await db.execute(select(Incident).where(Incident.id == UUID(str(incident_id))))
            incident = result.scalar_one_or_none()
            if incident is None:
                await websocket.close(code=1008, reason="Incident not found")
                return
            if incident.user_id != user.id and user.role not in {"dispatcher", "judge", "admin"}:
                await websocket.close(code=1008, reason="Not allowed")
                return
        await websocket_manager.stream_incident(websocket, incident_id)
    except WebSocketDisconnect:
        return
    except (RuntimeError, ValueError):
        return

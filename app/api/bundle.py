from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.incident import IncidentSource
from app.models.user import User
from app.schemas.sos import SOSTrigger
from app.services.classifier import classify_emergency
from app.services.country_registry import get_country_fallback_numbers
from app.services.geo import find_nearby_services
from app.services.offline_payload import generate_offline_payload
from app.services.private_profile import load_private_profile
from app.services.task_queue import task_queue
from app.services.mci import (
    get_mci_threshold,
    get_sos_ids_in_geohash,
    is_mci_candidate_priority,
    mci_geohash_cell,
    register_sos_in_geohash,
)
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)
router = APIRouter()


def _calculate_golden_hour_risk(priority: str, distance_km: float) -> float:
    """Calculates the Golden Hour Risk Index based on severity and nearest service."""
    if priority == "P1_CRITICAL":
        base = 0.95
    elif priority == "P2_HIGH":
        base = 0.70
    elif priority == "P3_MEDIUM":
        base = 0.40
    else:
        base = 0.15
        
    # Simple linear penalty: +2% risk per km
    distance_penalty = min(0.30, distance_km * 0.02)
    return min(1.0, round(base + distance_penalty, 2))


def _generate_action_plan(priority: str, services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    plan = []
    step = 1
    
    if priority in ("P1_CRITICAL", "P2_HIGH"):
        plan.append({
            "step": step,
            "action": "Dispatch emergency services via SOS.",
            "eta": "Immediate",
            "why": "Life-threatening severity requires immediate professional response."
        })
        step += 1
        
    if services:
        top_service = services[0]
        plan.append({
            "step": step,
            "action": f"Prepare for arrival of {top_service['name']}",
            "eta_minutes": max(2, int(top_service['distance_km'] * 1.5)), # Rough ETA
            "confidence": top_service['trust_score'],
            "why": top_service['explainable_trust']
        })
        step += 1
        
    plan.append({
        "step": step,
        "action": "Notify emergency contacts & broadcast to nearby mesh/volunteers.",
        "eta": "Immediate"
    })
    
    return plan


@router.post("/bundle")
async def get_emergency_bundle(
    payload: SOSTrigger,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The Golden Hour Rescue Engine endpoint.
    
    Returns a complete, structured Golden Hour Rescue Plan containing:
    - Deterministic severity triage
    - Trust-scored emergency services
    - Golden Hour Risk Index
    - Sequential action plan
    - Offline fallback payloads
    - Country-specific fallback emergency numbers
    """
    # 1. Deterministic Triage
    priority_label, confidence = classify_emergency(
        payload.description, payload.impact_force or 0, payload.sensor_payload, source=payload.source
    )
    
    # 2. Get Trust-Scored Services (Local DB/Cache first)
    # We fetch Medical and Safety services separately for the bundle structure
    medical_services = await find_nearby_services(
        payload.lat, payload.lng, db=db, types=["AMBULANCE", "TRAUMA", "HOSPITAL"], limit=5
    )
    safety_services = await find_nearby_services(
        payload.lat, payload.lng, db=db, types=["POLICE", "FIRE"], limit=3
    )
    vehicle_services = await find_nearby_services(
        payload.lat, payload.lng, db=db, types=["TOWING"], limit=3
    )
    
    all_services = medical_services + safety_services + vehicle_services
    needs_commit = False

    # 3. If no local services found, we would ideally trigger a background Overpass fetch here.
    # We use task_queue to queue it asynchronously so we don't block the bundle return.
    if not all_services:
        await task_queue.enqueue(
            db,
            "seed_overpass_bbox",
            {"lat": payload.lat, "lng": payload.lng},
            dedupe_key=f"seed_overpass_{round(payload.lat, 2)}_{round(payload.lng, 2)}"
        )
        needs_commit = True

    # 4. Fetch User Contacts
    private_profile = await load_private_profile(db, current_user)
    contacts = private_profile.get("emergency_contacts") or []

    # 5. Fallback Numbers
    fallback_numbers = get_country_fallback_numbers(payload.lat, payload.lng)

    # 6. Idempotency: Create or Fetch Incident
    from app.models.incident import Incident, IncidentStatus, PriorityEnum
    from sqlalchemy import select
    from datetime import datetime, timedelta, timezone

    # Look for an active incident for this user created in the last 5 minutes
    five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    existing_stmt = select(Incident).where(
        Incident.user_id == current_user.id,
        Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.ACKNOWLEDGED, IncidentStatus.ESCALATED]),
        Incident.created_at >= five_mins_ago
    )
    result = await db.execute(existing_stmt)
    incident = result.scalar_one_or_none()

    if not incident:
        # Create new incident if none exists
        incident = Incident(
            user_id=current_user.id,
            description=payload.description,
            priority=PriorityEnum(priority_label),
            triage_confidence=confidence,
            source=IncidentSource(payload.source),
            lat=payload.lat,
            lng=payload.lng,
            status=IncidentStatus.ACTIVE,
            metadata_json={"client_reference_id": payload.client_reference_id} if payload.client_reference_id else {}
        )
        db.add(incident)
        await db.flush()
        # Trigger escalation in background for the new incident
        await task_queue.enqueue_escalation(db, str(incident.id))
        await db.commit()
        await db.refresh(incident)

    nearest_dist = all_services[0]['distance_km'] if all_services else 15.0
    risk_index = _calculate_golden_hour_risk(priority_label, nearest_dist)
    action_plan = _generate_action_plan(priority_label, all_services)
    
    # 7. MCI Hot Path Detection. P4 roadside assistance is intentionally excluded
    # to avoid grouping non-casualty breakdowns with true emergency calls.
    mci_threshold = await get_mci_threshold()
    mci_cell = mci_geohash_cell(payload.lat, payload.lng)
    cluster_size = 0
    mci_pending = False
    if is_mci_candidate_priority(priority_label):
        cluster_size = await register_sos_in_geohash(payload.lat, payload.lng, str(incident.id), cell=mci_cell)
        mci_pending = cluster_size >= mci_threshold

    if mci_pending:
        incident_metadata = dict(incident.metadata_json or {})
        incident_metadata.update({"mci_pending": True, "mci_cell": mci_cell, "mci_hot_path_count": cluster_size})
        incident.metadata_json = incident_metadata
        # Enqueue background PostGIS verification
        await task_queue.enqueue(
            db,
            "mci_dbscan",
            {"lat": payload.lat, "lng": payload.lng, "cell": mci_cell, "trigger_incident_id": str(incident.id)},
            dedupe_key=f"mci_dbscan_{mci_cell}"
        )
        needs_commit = True
        provisional_payload = {
            "cell": mci_cell,
            "hot_path_count": cluster_size,
            "threshold": mci_threshold,
            "message": "Multiple casualties suspected nearby. Stay put unless in immediate danger.",
        }
        provisional_incident_ids = await get_sos_ids_in_geohash(mci_cell)
        for provisional_incident_id in provisional_incident_ids:
            await websocket_manager.publish_incident_event(provisional_incident_id, "mci_provisional", provisional_payload)
        await websocket_manager.publish_dashboard_event(
            "mci_provisional",
            {"incident_ids": provisional_incident_ids, **provisional_payload},
        )
        action_plan.insert(0, {
            "step": 0,
            "action": "Multiple casualties suspected nearby. DO NOT MOVE unless in immediate danger. Wait for unified dispatch.",
            "eta": "Immediate",
            "why": "Mass Casualty Incident (MCI) protocol engaged to prioritize critical resources."
        })

    if needs_commit:
        await db.commit()

    # 7. Generate Offline Payload
    offline_payload = generate_offline_payload(incident, all_services, contacts)

    return {
        "incident_id": str(incident.id),
        "severity": priority_label,
        "confidence_overall": confidence,
        "golden_hour_risk_index": risk_index,
        "recommended_action_plan": action_plan,
        "medical": medical_services,
        "safety": safety_services,
        "vehicle": vehicle_services,
        "contacts": {"user_emergency": [c.get("name") for c in contacts]},
        "offline_payload": offline_payload,
        "country_fallback": fallback_numbers,
        "mesh_relay_status": "standby",
        "mci_pending": mci_pending,
        "mci": {
            "pending": mci_pending,
            "cell": mci_cell if mci_pending else None,
            "hot_path_count": cluster_size,
            "threshold": mci_threshold,
        },
    }

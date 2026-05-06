from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.incident import Incident, IncidentSource, IncidentStatus, PriorityEnum
from app.services.task_queue import task_queue

logger = logging.getLogger(__name__)
router = APIRouter()

class MeshPacket(BaseModel):
    payload_b64: str = Field(..., min_length=8, max_length=12000)  # Base64 encoded JSON string
    signature: str = Field(..., min_length=64, max_length=64, pattern="^[0-9a-fA-F]{64}$")
    hops: int = Field(default=0, ge=0, le=12)


def _mesh_signing_key() -> str:
    return settings.MESH_RELAY_SIGNING_KEY or settings.SECRET_KEY


@router.post("/mesh-relay")
async def receive_mesh_relay(
    packet: MeshPacket,
    db: AsyncSession = Depends(get_db),
):
    """
    Mesh Relay Inbox.
    
    Accepts a compressed SOS packet forwarded by a peer device that has regained
    connectivity. Validates HMAC signature to prevent spam/abuse.
    """
    # 1. Verify Signature
    expected_sig = hmac.new(
        _mesh_signing_key().encode('utf-8'),
        packet.payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, packet.signature):
        logger.warning("Invalid mesh packet signature")
        raise HTTPException(status_code=401, detail="Invalid mesh signature")

    # 2. Decode payload
    try:
        decoded_bytes = base64.b64decode(packet.payload_b64, validate=True)
        if len(decoded_bytes) > settings.MAX_MESH_PAYLOAD_BYTES:
            raise ValueError("mesh payload too large")
        payload: Dict[str, Any] = json.loads(decoded_bytes.decode('utf-8'))
    except Exception as e:
        logger.warning(f"Invalid mesh packet received: {e}")
        raise HTTPException(status_code=400, detail="Invalid compressed payload")
        
    incident_id = payload.get("i")
    user_id = payload.get("u")
    lat = payload.get("l", [None, None])[0]
    lng = payload.get("l", [None, None])[1]
    priority = payload.get("p")
    
    try:
        incident_id = str(UUID(str(incident_id)))
        user_id = str(UUID(str(user_id)))
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid critical fields in mesh payload")

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="Invalid mesh coordinates")

    if not incident_id or lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Missing critical fields in mesh payload")

    # Queue the escalation. We use dedupe_key so if 5 different mesh peers all regain 
    # connectivity and upload the exact same packet, we only process it once.
    dedupe_key = f"mesh_relay_{incident_id}_{packet.signature}"
    
    await task_queue.enqueue(
        db,
        "process_mesh_relay",
        {
            "incident_id": incident_id,
            "user_id": user_id,
            "lat": lat,
            "lng": lng,
            "priority": priority,
            "hops": packet.hops
        },
        dedupe_key=dedupe_key,
        max_attempts=3
    )
    
    await db.commit()

    return {"status": "accepted", "message": "Mesh packet queued for processing"}


# Task queue handler for the mesh packet
async def handle_mesh_relay(payload: dict) -> None:
    """Task handler to process a mesh packet and ensure the incident exists."""
    incident_id = payload.get("incident_id")
    user_id = payload.get("user_id")
    lat = payload.get("lat")
    lng = payload.get("lng")
    priority_str = payload.get("priority") or "P1_CRITICAL"

    logger.info(f"Processing mesh relay packet for incident {incident_id} (user {user_id}) after {payload.get('hops')} hops.")
    
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        # 1. Check if the incident already exists (maybe another relay beat us to it)
        result = await db.execute(select(Incident).where(Incident.id == UUID(str(incident_id))))
        incident = result.scalar_one_or_none()
        
        if not incident:
            logger.info(f"Creating ghost incident {incident_id} from mesh payload.")
            try:
                priority_enum = PriorityEnum(priority_str)
            except ValueError:
                priority_enum = PriorityEnum.P1_CRITICAL

            incident = Incident(
                id=UUID(str(incident_id)),
                user_id=UUID(str(user_id)),
                description="OFFLINE SOS: Triggered via Mesh Relay (Bluetooth/SMS).",
                priority=priority_enum,
                source=IncidentSource.MANUAL,
                lat=lat,
                lng=lng,
                status=IncidentStatus.ACTIVE,
                metadata_json={"mesh_hops": payload.get("hops")}
            )
            db.add(incident)
            await db.flush()

        # 2. Trigger standard escalation
        await task_queue.enqueue_escalation(db, str(incident.id))
        await db.commit()

task_queue.register("process_mesh_relay", handle_mesh_relay)

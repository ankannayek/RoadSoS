from __future__ import annotations

<<<<<<< HEAD
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import insert, select
=======
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
<<<<<<< HEAD
from app.models.incident import Incident, IncidentResponderAttempt, IncidentStatus
from app.models.user import User
from app.models.volunteer import Volunteer
from app.schemas.volunteer import VolunteerCreate, VolunteerIncidentResponse, VolunteerIncidentResponseOut, VolunteerOut, VolunteerUpdate
from app.services.geo import find_nearby_volunteers
from app.services.websocket_manager import websocket_manager
=======
from app.models.user import User
from app.models.volunteer import Volunteer
from app.schemas.volunteer import VolunteerCreate, VolunteerOut, VolunteerUpdate
from app.services.geo import find_nearby_volunteers
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0

router = APIRouter()


@router.post("/me", response_model=VolunteerOut, status_code=status.HTTP_201_CREATED)
async def create_or_update_volunteer_profile(payload: VolunteerCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Volunteer).where(Volunteer.user_id == current_user.id))
    volunteer = result.scalar_one_or_none()
    if volunteer is None:
        volunteer = Volunteer(user_id=current_user.id, name=payload.name, phone=payload.phone)
        db.add(volunteer)
    volunteer.name = payload.name
    volunteer.phone = payload.phone
    volunteer.skills = payload.skills
    volunteer.available = payload.available
    volunteer.set_location_from_coords(payload.lat, payload.lng)
    if current_user.role == "user":
        current_user.role = "volunteer"
    await db.commit()
    await db.refresh(volunteer)
    return volunteer


@router.patch("/me", response_model=VolunteerOut)
async def update_volunteer_profile(payload: VolunteerUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Volunteer).where(Volunteer.user_id == current_user.id))
    volunteer = result.scalar_one_or_none()
    if volunteer is None:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")
    data = payload.model_dump(exclude_unset=True)
    lat = data.pop("lat", None)
    lng = data.pop("lng", None)
    for key, value in data.items():
        setattr(volunteer, key, value)
    if lat is not None or lng is not None:
        volunteer.set_location_from_coords(lat if lat is not None else volunteer.lat, lng if lng is not None else volunteer.lng)
    await db.commit()
    await db.refresh(volunteer)
    return volunteer


@router.post("/toggle-availability")
async def toggle_availability(available: bool, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Volunteer).where(Volunteer.user_id == current_user.id))
    volunteer = result.scalar_one_or_none()
    if volunteer is None:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")
    volunteer.available = available
    await db.commit()
    return {"status": "updated", "available": available}


@router.get("/nearby")
async def get_nearby_volunteers(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    volunteers = await find_nearby_volunteers(lat, lng, db=db, radius_km=radius_km)
    return {"volunteers": volunteers}
<<<<<<< HEAD


@router.post("/incidents/{incident_id}/respond", response_model=VolunteerIncidentResponseOut)
async def respond_to_incident(
    incident_id: UUID,
    payload: VolunteerIncidentResponse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    volunteer_result = await db.execute(select(Volunteer).where(Volunteer.user_id == current_user.id))
    volunteer = volunteer_result.scalar_one_or_none()
    if volunteer is None:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")

    incident_result = await db.execute(
        select(Incident).where(Incident.id == incident_id).with_for_update()
    )
    incident = incident_result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status not in {IncidentStatus.ACTIVE, IncidentStatus.ESCALATED, IncidentStatus.ACKNOWLEDGED}:
        raise HTTPException(status_code=409, detail="Incident is not accepting responder updates")

    status_value = "declined"
    if payload.action == "accept":
        if incident.accepted_responder_id and incident.accepted_responder_id != volunteer.id:
            raise HTTPException(status_code=409, detail="Incident already has an accepted responder")
        incident.accepted_responder_id = volunteer.id
        incident.status = IncidentStatus.ACKNOWLEDGED
        status_value = "accepted"

    await db.execute(
        insert(IncidentResponderAttempt).values(
            incident_id=incident.id,
            responder_type="volunteer",
            responder_id=volunteer.id,
            channel="app",
            tier="responder",
            status=status_value,
            payload={"note": payload.note, "user_id": str(current_user.id)},
        )
    )
    await db.commit()
    await db.refresh(incident)

    await websocket_manager.publish_incident_event(
        str(incident.id),
        "responder_updated",
        {"volunteer_id": str(volunteer.id), "status": status_value, "incident_status": incident.status.value},
    )
    await websocket_manager.publish_dashboard_event(
        "incident_responder_updated",
        {"incident_id": str(incident.id), "volunteer_id": str(volunteer.id), "status": status_value},
    )
    return VolunteerIncidentResponseOut(
        status=status_value,
        incident_id=incident.id,
        volunteer_id=volunteer.id,
        incident_status=incident.status.value,
    )
=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0

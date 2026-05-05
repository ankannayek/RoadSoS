from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.volunteer import Volunteer
from app.schemas.volunteer import VolunteerCreate, VolunteerOut, VolunteerUpdate
from app.services.geo import find_nearby_volunteers

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

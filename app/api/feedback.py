from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.feedback import Feedback
from app.models.incident import Incident
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services.feedback import recompute_volunteer_rating

router = APIRouter()


@router.post("/", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def create_feedback(payload: FeedbackCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    incident_result = await db.execute(select(Incident).where(Incident.id == payload.incident_id, Incident.user_id == current_user.id))
    if incident_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    feedback = Feedback(incident_id=payload.incident_id, volunteer_id=payload.volunteer_id, rating=payload.rating, note=payload.note)
    db.add(feedback)
    await db.flush()
    if payload.volunteer_id:
        await recompute_volunteer_rating(db, payload.volunteer_id)
    await db.commit()
    await db.refresh(feedback)
    return feedback

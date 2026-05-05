from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.helper import HelperAnswer, HelperQuery
from app.services.rag import hybrid_rag_pipeline

router = APIRouter()


@router.post("/query", response_model=HelperAnswer)
async def helper_query(payload: HelperQuery, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await hybrid_rag_pipeline.answer(
        db,
        payload.query,
        lat=payload.lat,
        lng=payload.lng,
        include_services=payload.include_services,
    )

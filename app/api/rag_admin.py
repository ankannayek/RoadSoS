from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db
from app.models.user import User
from app.services.rag_ingestion import rag_ingestion_pipeline

router = APIRouter()


@router.post("/ingest-default")
async def ingest_default_knowledge(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    path = Path(__file__).resolve().parents[2] / "knowledge" / "road_emergency_scenarios.txt"
    chunks = await rag_ingestion_pipeline.ingest_file(db, path, source_key="road-emergency-scenarios", title="RoadSoS Road Emergency Scenario Guide")
    return {"status": "ingested", "chunks": chunks}

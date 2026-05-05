from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    incident_id: UUID
    volunteer_id: Optional[UUID] = None
    rating: int = Field(..., ge=1, le=5)
    note: Optional[str] = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    id: UUID
    incident_id: UUID
    volunteer_id: Optional[UUID]
    rating: int
    note: Optional[str]

    model_config = {"from_attributes": True}

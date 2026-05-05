from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VolunteerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=5, max_length=20)
    skills: List[str] = Field(default_factory=list)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    available: bool = False


class VolunteerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, min_length=5, max_length=20)
    skills: Optional[List[str]] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    available: Optional[bool] = None


class VolunteerOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    phone: str
    available: bool
    rating: float
    skills: List[str] = []
    lat: Optional[float] = None
    lng: Optional[float] = None
    distance_km: Optional[float] = None
    confidence_score: Optional[float] = None

    model_config = {"from_attributes": True}

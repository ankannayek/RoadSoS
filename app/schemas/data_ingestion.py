from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EmergencyServiceIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    type: str = Field(..., min_length=2, max_length=30)
    phone: Optional[str] = Field(default=None, max_length=20)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    capacity: Optional[int] = Field(default=None, ge=0, le=100000)
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    source: str = Field(default="user_report", max_length=40)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata_json")
    @classmethod
    def limit_metadata_size(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if len(str(value)) > 5000:
            raise ValueError("metadata_json is too large")
        return value


class ServiceImportRequest(BaseModel):
    source: str = Field(..., pattern="^(osm|gov|nhai|user_report|seed|partner|manual)$")
    dry_run: bool = False
    services: List[EmergencyServiceIn] = Field(default_factory=list, max_length=500)


class ServiceImportResponse(BaseModel):
    source: str
    dry_run: bool
    received: int
    inserted_or_updated: int
    rejected: int
    warnings: List[str] = Field(default_factory=list)


class ServiceReportCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    type: str = Field(..., min_length=2, max_length=30)
    phone: Optional[str] = Field(default=None, max_length=20)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    note: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("type")
    @classmethod
    def validate_service_report_type(cls, value: str) -> str:
        cleaned = value.strip().upper().replace(" ", "_")
        allowed = {"AMBULANCE", "TRAUMA", "HOSPITAL", "POLICE", "FIRE", "TOWING", "MECHANIC"}
        if cleaned not in allowed:
            raise ValueError("Unsupported service type")
        return cleaned


class ServiceReportReview(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    confidence_score: float = Field(default=0.65, ge=0, le=1)


class ServiceReportOut(BaseModel):
    id: UUID
    name: str
    type: str
    phone: Optional[str]
    lat: float
    lng: float
    note: Optional[str]
    verification_status: str

    model_config = {"from_attributes": True}

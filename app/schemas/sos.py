from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LocationPayload(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    accuracy_m: Optional[float] = Field(default=None, ge=0, le=5000)
    speed_mps: Optional[float] = Field(default=None, ge=0, le=120)
    heading_deg: Optional[float] = Field(default=None, ge=0, le=360)


class SOSTrigger(BaseModel):
    description: str = Field(..., min_length=3, max_length=1000)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    impact_force: Optional[float] = Field(default=None, ge=0, le=100)
    source: str = Field(default="manual", pattern="^(manual|auto_detect|voice|silent|bystander)$")
    silent: bool = False
    bystander_mode: bool = False
    victim_name: Optional[str] = Field(default=None, max_length=100)
    victim_phone: Optional[str] = Field(default=None, max_length=20)
    sensor_payload: Dict[str, Any] = Field(default_factory=dict)
    client_reference_id: Optional[str] = Field(default=None, max_length=64, description="Idempotency key")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


class SOSResponse(BaseModel):
    incident_id: UUID
    priority: str
    triage_confidence: float
    volunteers_notified: int = 0
    services_notified: int = 0
    estimated_response_time: str
    message: str = "SOS received. Help dispatch has started."


class IncidentOut(BaseModel):
    id: UUID
    user_id: UUID
    description: str
    priority: str
    triage_confidence: float
    source: str
    silent: bool
    bystander_mode: bool
    lat: float
    lng: float
    status: str
    cluster_id: Optional[UUID] = None
    is_mci: bool = False
    is_mci_coordinator: bool = False
    accepted_responder_id: Optional[UUID] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IncidentStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(acknowledged|resolved|cancelled)$")
    note: Optional[str] = Field(default=None, max_length=500)


class LiveLocationUpdate(LocationPayload):
    incident_id: UUID
    battery_percent: Optional[int] = Field(default=None, ge=0, le=100)
    timestamp: Optional[datetime] = None


class OfflineServicesResponse(BaseModel):
    geohash: str
    services: List[Dict[str, Any]]
    ttl_seconds: int = 86400


class SMSFallbackPayload(BaseModel):
    sms_to: List[str]
    message: str
    lat: float
    lng: float
    maps_url: str
    ttl_seconds: int = 86400

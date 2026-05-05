from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardIncident(BaseModel):
    id: UUID
    user_id: UUID
    priority: str
    status: str
    source: str
    silent: bool
    bystander_mode: bool
    lat: float
    lng: float
    description_preview: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    age_seconds: Optional[int] = None
    notifications_sent: int = 0
    feedback_rating: Optional[float] = None


class DashboardMetrics(BaseModel):
    window_hours: int
    active_incidents: int
    escalated_incidents: int
    resolved_incidents: int
    cancelled_incidents: int
    avg_resolution_seconds: Optional[float] = None
    avg_feedback_rating: Optional[float] = None
    incidents_by_priority: Dict[str, int] = Field(default_factory=dict)
    notifications_by_channel: Dict[str, int] = Field(default_factory=dict)
    notifications_by_status: Dict[str, int] = Field(default_factory=dict)


class IncidentTimelineEvent(BaseModel):
    event_type: str
    created_at: datetime
    channel: Optional[str] = None
    recipient_type: Optional[str] = None
    recipient: Optional[str] = None
    status: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

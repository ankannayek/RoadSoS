from __future__ import annotations

import enum
import uuid

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, String, Text, event, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class PriorityEnum(str, enum.Enum):
    P1_CRITICAL = "P1_CRITICAL"
    P2_HIGH = "P2_HIGH"
    P3_MEDIUM = "P3_MEDIUM"
    P4_LOW = "P4_LOW"


class IncidentStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class IncidentSource(str, enum.Enum):
    MANUAL = "manual"
    AUTO_DETECT = "auto_detect"
    VOICE = "voice"
    SILENT = "silent"
    BYSTANDER = "bystander"


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    priority = Column(Enum(PriorityEnum, name="priorityenum"), nullable=False, index=True)
    triage_confidence = Column(Float, nullable=False, default=0)
    source = Column(Enum(IncidentSource, name="incidentsource"), nullable=False, default=IncidentSource.MANUAL)
    silent = Column(Boolean, nullable=False, default=False)
    bystander_mode = Column(Boolean, nullable=False, default=False)
    victim_name = Column(String(100), nullable=True)
    victim_phone = Column(String(20), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    location = Column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    status = Column(Enum(IncidentStatus, name="incidentstatus"), default=IncidentStatus.ACTIVE, nullable=False, index=True)
<<<<<<< HEAD
    accepted_responder_id = Column(UUID(as_uuid=True), ForeignKey("volunteers.id", ondelete="SET NULL"), nullable=True)
=======
    accepted_responder_id = Column(UUID(as_uuid=True), nullable=True)
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="incidents")
    feedback = relationship("Feedback", back_populates="incident")


@event.listens_for(Incident, "before_insert")
@event.listens_for(Incident, "before_update")
def set_incident_location(mapper, connection, target):
    if target.lat is not None and target.lng is not None:
        target.location = WKTElement(f"POINT({target.lng} {target.lat})", srid=4326)


class IncidentResponderAttempt(Base):
    __tablename__ = "incident_responder_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    responder_type = Column(String(30), nullable=False)  # volunteer | service | contact | dashboard
    responder_id = Column(UUID(as_uuid=True), nullable=True)
<<<<<<< HEAD
    channel = Column(String(30), nullable=False)  # fcm | sms | websocket | dashboard | app
=======
    channel = Column(String(30), nullable=False)  # fcm | whatsapp | sms | websocket | dashboard
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    tier = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

from __future__ import annotations

import uuid

from geoalchemy2 import Geography
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class EmergencyService(Base):
    __tablename__ = "emergency_services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    type = Column(String(30), nullable=False, index=True)  # AMBULANCE, TRAUMA, HOSPITAL, POLICE, TOWING, FIRE
    phone = Column(String(20), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    location = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    capacity = Column(Integer, nullable=True)
    confidence_score = Column(Numeric(4, 3), nullable=False, default=0.50)
    source = Column(String(40), nullable=False, default="user_report")
    metadata_json = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ServiceReport(Base):
    __tablename__ = "service_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id = Column(UUID(as_uuid=True), nullable=True)
    reporter_user_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(150), nullable=False)
    type = Column(String(30), nullable=False)
    phone = Column(String(20), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    note = Column(Text, nullable=True)
    verification_status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

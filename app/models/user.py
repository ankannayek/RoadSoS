from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    blood_group = Column(String(10), nullable=True)
    medical_conditions = Column(String(500), nullable=True)
    allergies = Column(String(300), nullable=True)
    emergency_contacts = Column(JSONB, nullable=True)
    preferred_language = Column(String(12), nullable=False, default="en")
    role = Column(String(30), nullable=False, default="user")
    fcm_tokens = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    incidents = relationship("Incident", back_populates="user")
    volunteer_profile = relationship("Volunteer", back_populates="user", uselist=False)

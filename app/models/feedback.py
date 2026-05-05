from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("incident_id", "volunteer_id", name="uq_feedback_incident_volunteer"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    volunteer_id = Column(UUID(as_uuid=True), ForeignKey("volunteers.id", ondelete="SET NULL"), nullable=True, index=True)
    rating = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    incident = relationship("Incident", back_populates="feedback")
    volunteer = relationship("Volunteer", back_populates="feedback")

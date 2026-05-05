from __future__ import annotations

import uuid

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy import ARRAY, Boolean, Column, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class Volunteer(Base):
    __tablename__ = "volunteers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    available = Column(Boolean, default=False, nullable=False, index=True)
    rating = Column(Float, default=3.0, nullable=False)
    completed_responses = Column(Float, default=0, nullable=False)
    cancelled_responses = Column(Float, default=0, nullable=False)
    skills = Column(ARRAY(String), default=list)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    location = Column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    last_active = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="volunteer_profile")
    feedback = relationship("Feedback", back_populates="volunteer")

    def set_location_from_coords(self, lat: float, lng: float) -> None:
        self.lat = lat
        self.lng = lng
        self.location = WKTElement(f"POINT({lng} {lat})", srid=4326)

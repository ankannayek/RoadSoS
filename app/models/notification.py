from __future__ import annotations

import uuid

<<<<<<< HEAD
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
=======
from sqlalchemy import Column, DateTime, String, Text, func
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
<<<<<<< HEAD
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
=======
    incident_id = Column(UUID(as_uuid=True), nullable=True, index=True)
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    recipient_type = Column(String(30), nullable=False)
    recipient = Column(String(255), nullable=True)
    channel = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False)
    provider_message_id = Column(String(255), nullable=True)
    error = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

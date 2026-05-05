from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class RAGSource(Base):
    __tablename__ = "rag_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_key = Column(String(160), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    source_type = Column(String(40), nullable=False, default="static")
    version = Column(String(40), nullable=False, default="v1")
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RAGChunk(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (UniqueConstraint("source_id", "chunk_index", name="uq_rag_source_chunk"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("rag_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    heading = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False, default=0)
    embedding_model = Column(String(80), nullable=False, default="hashing-v1")
    # The actual pgvector column is created in schema.sql. SQLAlchemy keeps this
    # model light so the app can boot even if pgvector is not installed locally.
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

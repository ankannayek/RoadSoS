from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HelperQuery(BaseModel):
    query: str = Field(..., min_length=3, max_length=1200)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    include_services: bool = True
    language: str = Field(default="en", max_length=12)


class RAGCitation(BaseModel):
    source_key: str
    title: str
    chunk_index: int
    heading: Optional[str] = None
    score: float


class HelperAnswer(BaseModel):
    answer: str
    confidence: float
    citations: List[RAGCitation]
    matched_services: List[Dict[str, Any]] = Field(default_factory=list)
    safety_notice: str

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.classifier import EMERGENCY_KEYWORDS
from app.services.geo import find_nearby_services
from app.services.llm import grounded_llm_client
from app.services.rag_ingestion import build_embedding_provider, vector_literal

logger = logging.getLogger(__name__)

SAFETY_NOTICE = (
    "This helper is for general first-aid and road-safety guidance only. "
    "For immediate danger, trigger SOS or call local emergency services first. "
    "Do not delay professional help."
)

SOS_FIRST_PREFIX = (
    "THIS SOUNDS LIKE AN EMERGENCY. TRIGGER SOS OR CALL 112 (or your local "
    "emergency number) NOW. Do not delay; get professional help first. "
    "The guidance below is for while you wait for responders.\n\n"
)


def _detect_emergency_in_query(query: str) -> bool:
    """Check if the user's query contains life-threatening emergency keywords.

    Per RAG spec: 'If life risk exists, first line must tell the user to trigger
    SOS/call emergency services.' This runs at the start of the RAG answer path.
    """
    lowered = query.lower()
    return any(keyword in lowered for keyword in EMERGENCY_KEYWORDS)


@dataclass
class RetrievedChunk:
    source_key: str
    title: str
    chunk_index: int
    heading: str | None
    text: str
    score: float


class HybridRAGPipeline:
    def __init__(self) -> None:
        self.embedding_provider = build_embedding_provider()

    async def _semantic_search(self, db: AsyncSession, query: str, top_k: int) -> list[RetrievedChunk]:
        try:
            embedding = vector_literal(await self.embedding_provider.embed(query, retry=False))
            result = await db.execute(
                text(
                    """
                    SELECT rs.source_key, rs.title, rc.chunk_index, rc.heading, rc.text,
                           GREATEST(0, 1 - (rc.embedding <=> (:embedding)::vector)) AS score
                    FROM rag_chunks rc
                    JOIN rag_sources rs ON rs.id = rc.source_id
                    WHERE rs.is_active = true AND rc.embedding IS NOT NULL
                    ORDER BY rc.embedding <=> (:embedding)::vector
                    LIMIT :limit
                    """
                ),
                {"embedding": embedding, "limit": top_k},
            )
            return [RetrievedChunk(**dict(row)) for row in result.mappings().all()]
        except Exception as exc:
            logger.warning("Semantic RAG search failed; falling back to keyword only: %s", exc)
            return []

    async def _keyword_search(self, db: AsyncSession, query: str, top_k: int) -> list[RetrievedChunk]:
        result = await db.execute(
            text(
                """
                SELECT rs.source_key, rs.title, rc.chunk_index, rc.heading, rc.text,
                       ts_rank_cd(rc.search_vector, websearch_to_tsquery('english', :query)) AS score
                FROM rag_chunks rc
                JOIN rag_sources rs ON rs.id = rc.source_id
                WHERE rs.is_active = true
                  AND rc.search_vector @@ websearch_to_tsquery('english', :query)
                ORDER BY score DESC
                LIMIT :limit
                """
            ),
            {"query": query, "limit": top_k},
        )
        return [RetrievedChunk(**dict(row)) for row in result.mappings().all()]

    def _rrf(self, semantic: list[RetrievedChunk], keyword: list[RetrievedChunk]) -> list[RetrievedChunk]:
        merged: dict[tuple[str, int], RetrievedChunk] = {}
        scores: dict[tuple[str, int], float] = {}
        for source_list, weight in ((semantic, 0.55), (keyword, 0.45)):
            for rank, chunk in enumerate(source_list, start=1):
                key = (chunk.source_key, chunk.chunk_index)
                merged[key] = chunk
                scores[key] = scores.get(key, 0.0) + weight * (1 / (60 + rank)) + max(float(chunk.score or 0), 0) * 0.05
        ranked = []
        for key, chunk in merged.items():
            ranked.append(RetrievedChunk(chunk.source_key, chunk.title, chunk.chunk_index, chunk.heading, chunk.text, round(scores[key], 4)))
        return sorted(ranked, key=lambda c: c.score, reverse=True)

    def _build_context(self, chunks: list[RetrievedChunk]) -> list[str]:
        context_parts = []
        char_budget = settings.RAG_MAX_CONTEXT_CHARS
        for chunk in chunks:
            heading = f"[{chunk.heading}]\n" if chunk.heading else ""
            part = f"{heading}{chunk.text}".strip()
            if len("\n\n".join(context_parts + [part])) > char_budget:
                break
            context_parts.append(part)
        return context_parts

    async def _compose_grounded_answer(self, query: str, chunks: list[RetrievedChunk], is_emergency_query: bool) -> tuple[str, float]:
        if not chunks:
            base_answer = (
                "I do not have a reliable grounded answer in the emergency knowledge base for that question. "
                "Trigger SOS or call local emergency services if anyone may be in danger."
            )
            if is_emergency_query:
                return SOS_FIRST_PREFIX + base_answer, 0.0
            return base_answer, 0.0

        context_parts = self._build_context(chunks)
        context = "\n\n---\n\n".join(context_parts[:6])
        confidence = round(min(0.95, 0.35 + sum(c.score for c in chunks[:5])), 3)

        if confidence >= settings.RAG_MIN_CONFIDENCE:
            try:
                llm_answer = await grounded_llm_client.answer(query, context)
                if llm_answer:
                    if is_emergency_query:
                        return SOS_FIRST_PREFIX + llm_answer, confidence
                    return llm_answer, confidence
            except Exception as exc:  # pragma: no cover
                logger.warning("Grounded LLM answer failed; using extractive fallback: %s", exc)

        answer = (
            "Based on the RoadSoS emergency guide:\n\n"
            + "\n\n".join(f"- {part[:900]}" for part in context_parts[:4])
            + "\n\nImmediate rule: if there is life risk, fire, trapped person, heavy bleeding, unconsciousness, or threat to safety, trigger SOS/call emergency services first."
        )
        if is_emergency_query:
            answer = SOS_FIRST_PREFIX + answer
        return answer, confidence

    async def answer(self, db: AsyncSession, query: str, lat: float | None = None, lng: float | None = None, include_services: bool = True) -> dict[str, Any]:
        # Emergency guardrail from the RAG spec.
        # If the query contains life-threatening keywords, the first line
        # of the answer MUST tell the user to trigger SOS / call 112.
        is_emergency_query = _detect_emergency_in_query(query)

        semantic = await self._semantic_search(db, query, settings.RAG_TOP_K_SEMANTIC)
        keyword = await self._keyword_search(db, query, settings.RAG_TOP_K_KEYWORD)
        chunks = self._rrf(semantic, keyword)[:8]
        answer, confidence = await self._compose_grounded_answer(query, chunks, is_emergency_query)

        services: list[dict[str, Any]] = []
        if include_services and lat is not None and lng is not None:
            services = await find_nearby_services(lat, lng, db=db, types=["AMBULANCE", "TRAUMA", "HOSPITAL", "POLICE", "FIRE", "TOWING"], limit=5)

        return {
            "answer": answer,
            "confidence": confidence,
            "emergency_detected": is_emergency_query,
            "citations": [
                {"source_key": c.source_key, "title": c.title, "chunk_index": c.chunk_index, "heading": c.heading, "score": c.score}
                for c in chunks[:5]
            ],
            "matched_services": services,
            "safety_notice": SAFETY_NOTICE,
        }


hybrid_rag_pipeline = HybridRAGPipeline()

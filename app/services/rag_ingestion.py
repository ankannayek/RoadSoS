from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
HEADING_RE = re.compile(r"^(#{1,3}\s+|SCENARIO\s+\d+[:\.-]|PIPELINE\s+\d+[:\.-]|[A-Z][A-Z0-9 /&()\-]{8,}:)")


@dataclass
class Chunk:
    index: int
    heading: str | None
    text: str
    token_count: int


class SemanticChunker:
    def __init__(self, max_tokens: int = 260, overlap_tokens: int = 45) -> None:
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def _tokens(self, text_value: str) -> list[str]:
        return TOKEN_RE.findall(text_value)

    def split(self, document: str) -> list[Chunk]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", document) if p.strip()]
        chunks: list[Chunk] = []
        current: list[str] = []
        current_heading: str | None = None

        def flush() -> None:
            nonlocal current
            if not current:
                return
            text_value = "\n\n".join(current).strip()
            tokens = self._tokens(text_value)
            chunks.append(Chunk(len(chunks), current_heading, text_value, len(tokens)))
            if self.overlap_tokens and tokens:
                current = [" ".join(tokens[-self.overlap_tokens :])]
            else:
                current = []

        for para in paragraphs:
            if HEADING_RE.match(para):
                flush()
                current_heading = para.replace("#", "").strip()[:255]
            candidate = "\n\n".join(current + [para])
            if len(self._tokens(candidate)) > self.max_tokens and current:
                flush()
            current.append(para)
        flush()
        return [chunk for chunk in chunks if chunk.text]


class EmbeddingProvider(Protocol):
    model_name: str

    async def embed(self, text_value: str) -> list[float]:
        ...


class HashingEmbeddingProvider:
    model_name = "hashing-v1"

    def __init__(self, dim: int = settings.RAG_EMBEDDING_DIM) -> None:
        self.dim = dim

    async def embed(self, text_value: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in TOKEN_RE.findall(text_value.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [round(v / norm, 6) for v in vector]


class OpenAIEmbeddingProvider:
    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings")
        self.model_name = settings.OPENAI_EMBEDDING_MODEL

    async def embed(self, text_value: str) -> list[float]:
        body = {"model": settings.OPENAI_EMBEDDING_MODEL, "input": text_value, "dimensions": settings.RAG_EMBEDDING_DIM}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            return [float(v) for v in data["data"][0]["embedding"]]


def build_embedding_provider() -> EmbeddingProvider:
    if settings.RAG_EMBEDDING_PROVIDER.lower() == "openai" and settings.OPENAI_API_KEY:
        return OpenAIEmbeddingProvider()
    return HashingEmbeddingProvider()


def vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


class RAGIngestionPipeline:
    def __init__(self) -> None:
        self.chunker = SemanticChunker()
        self.embedding_provider = build_embedding_provider()

    async def ingest_text(self, db: AsyncSession, source_key: str, title: str, content: str, source_type: str = "static", version: str = "v1") -> int:
        chunks = self.chunker.split(content)
        source_id_result = await db.execute(
            text(
                """
                INSERT INTO rag_sources (source_key, title, source_type, version, is_active, metadata_json)
                VALUES (:source_key, :title, :source_type, :version, true, '{}'::jsonb)
                ON CONFLICT (source_key) DO UPDATE
                  SET title = EXCLUDED.title, source_type = EXCLUDED.source_type, version = EXCLUDED.version,
                      is_active = true, updated_at = NOW()
                RETURNING id
                """
            ),
            {"source_key": source_key, "title": title, "source_type": source_type, "version": version},
        )
        source_id = source_id_result.scalar_one()
        await db.execute(text("DELETE FROM rag_chunks WHERE source_id = :source_id"), {"source_id": source_id})
        for chunk in chunks:
            embedding = vector_literal(await self.embedding_provider.embed(chunk.text))
            await db.execute(
                text(
                    """
                    INSERT INTO rag_chunks (source_id, chunk_index, heading, text, token_count, embedding_model, embedding, search_vector, metadata_json)
                    VALUES (:source_id, :chunk_index, :heading, :text, :token_count, :embedding_model, (:embedding)::vector,
                            to_tsvector('english', :text), '{}'::jsonb)
                    """
                ),
                {
                    "source_id": source_id,
                    "chunk_index": chunk.index,
                    "heading": chunk.heading,
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                    "embedding_model": self.embedding_provider.model_name,
                    "embedding": embedding,
                },
            )
        await db.commit()
        return len(chunks)

    async def ingest_file(self, db: AsyncSession, path: str | Path, source_key: str | None = None, title: str | None = None) -> int:
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        return await self.ingest_text(db, source_key or path.stem, title or path.name, content)


rag_ingestion_pipeline = RAGIngestionPipeline()

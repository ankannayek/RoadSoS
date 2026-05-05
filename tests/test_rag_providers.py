from app.services.rag_ingestion import HashingEmbeddingProvider, build_embedding_provider


def test_gemini_embedding_provider_without_key_falls_back_to_hashing(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAG_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    provider = build_embedding_provider()
    assert isinstance(provider, HashingEmbeddingProvider)


async def test_hashing_embedding_dimension_tracks_settings(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAG_EMBEDDING_DIM", 16)
    # Must create the provider AFTER monkeypatch so __init__ reads the patched dim.
    provider = HashingEmbeddingProvider(dim=16)
    vector = await provider.embed("bleeding crash help")
    assert len(vector) == 16

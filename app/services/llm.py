from __future__ import annotations

import httpx

from app.core.config import settings


class GroundedLLMClient:
    async def answer(self, query: str, context: str) -> str | None:
        if not settings.RAG_LLM_ENABLED or settings.RAG_LLM_PROVIDER.lower() != "openai" or not settings.OPENAI_API_KEY:
            return None
        messages = [
            {
                "role": "system",
                "content": (
                    "You are RoadSoS Helper Bot. Answer only from the provided context. "
                    "Do not invent facts. If the context is insufficient, say that you do not have enough grounded information. "
                    "For immediate danger, tell the user to trigger SOS or call local emergency services first. "
                    "Keep the answer practical and concise."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ]
        body = {"model": settings.OPENAI_CHAT_MODEL, "messages": messages, "temperature": 0.1, "max_tokens": 550}
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()


grounded_llm_client = GroundedLLMClient()

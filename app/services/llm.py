from __future__ import annotations

import httpx

from app.core.config import settings


class GroundedLLMClient:
    async def answer(self, query: str, context: str) -> str | None:
<<<<<<< HEAD
        if not settings.RAG_LLM_ENABLED:
=======
        if not settings.RAG_LLM_ENABLED or settings.RAG_LLM_PROVIDER.lower() != "openai" or not settings.OPENAI_API_KEY:
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
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
<<<<<<< HEAD
        provider = settings.RAG_LLM_PROVIDER.lower()
        if provider == "groq" and settings.GROQ_API_KEY:
            return await self._groq_answer(messages)
        if provider in {"groq", "gemini"} and settings.GEMINI_API_KEY:
            return await self._gemini_answer(query, context)
        return None

    async def _groq_answer(self, messages: list[dict[str, str]]) -> str:
        body = {"model": settings.GROQ_CHAT_MODEL, "messages": messages, "temperature": 0.1, "max_tokens": 550}
        async with httpx.AsyncClient(timeout=settings.RAG_LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
=======
        body = {"model": settings.OPENAI_CHAT_MODEL, "messages": messages, "temperature": 0.1, "max_tokens": 550}
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

<<<<<<< HEAD
    async def _gemini_answer(self, query: str, context: str) -> str:
        model = settings.GEMINI_CHAT_MODEL.removeprefix("models/")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are RoadSoS Helper Bot. Answer only from the provided context. "
                            "Do not invent facts. If the context is insufficient, say that you do not have enough grounded information. "
                            "For immediate danger, tell the user to trigger SOS or call local emergency services first. "
                            "Keep the answer practical and concise."
                        )
                    }
                ]
            },
            "contents": [{"role": "user", "parts": [{"text": f"Context:\n{context}\n\nQuestion: {query}"}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 550},
        }
        async with httpx.AsyncClient(timeout=settings.RAG_LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(url, params={"key": settings.GEMINI_API_KEY}, json=body)
            response.raise_for_status()
            data = response.json()
            parts = data["candidates"][0]["content"].get("parts", [])
            return "\n".join(part.get("text", "") for part in parts).strip()

=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0

grounded_llm_client = GroundedLLMClient()

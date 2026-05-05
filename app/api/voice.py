from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/voice")
async def voice_sos(
    audio: UploadFile = File(...),
    lat: float = 0.0,
    lng: float = 0.0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Optional Accessibility Endpoint: Voice SOS.
    
    Allows trapped or visually impaired users to speak a 5-10 second SOS message.
    Uses Groq's extremely fast Whisper API to transcribe the audio, then feeds the 
    transcription directly into the deterministic classifier via the /emergency/bundle endpoint.
    
    Falls back gracefully if Groq is unavailable.
    """
    
    if not settings.GROQ_API_KEY:
        # Graceful fallback: return a flag telling the frontend to use manual SOS
        logger.warning("Voice SOS attempted but GROQ_API_KEY is not configured.")
        return {
            "status": "fallback",
            "message": "Voice transcription unavailable. Please use manual or silent SOS buttons.",
            "transcription": None
        }

    # Restrict file size (e.g., max 1MB for a short audio clip)
    content = await audio.read()
    if len(content) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large. Max 1MB.")
        
    try:
        import groq
        client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)
        
        # We must write the bytes to a temp file or file-like object because 
        # the Groq client expects a file tuple (filename, file_obj)
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
            
        try:
            with open(tmp_path, "rb") as file_obj:
                transcription = await client.audio.transcriptions.create(
                    file=(audio.filename or "audio.m4a", file_obj.read()),
                    model="whisper-large-v3-turbo",
                    prompt="Emergency rescue SOS call. Car crash, accident, bleeding, help.",
                    response_format="text",
                    temperature=0.0
                )
        finally:
            os.remove(tmp_path)
            
        transcribed_text = str(transcription).strip()
        logger.info(f"Voice SOS transcribed: '{transcribed_text}'")
        
        # We now feed this transcribed text into the bundle/classifier
        from app.schemas.sos import SOSTrigger
        from app.api.bundle import get_emergency_bundle
        
        payload = SOSTrigger(
            description=f"Voice transcribed: {transcribed_text}",
            lat=lat,
            lng=lng,
            source="voice"
        )
        
        # Get the full Golden Hour bundle using the transcribed text
        bundle = await get_emergency_bundle(payload, db=db, current_user=current_user)
        
        return {
            "status": "success",
            "transcription": transcribed_text,
            "bundle": bundle
        }

    except ImportError:
        logger.error("groq package not installed. Cannot use Voice SOS.")
        return {"status": "fallback", "message": "Voice service not installed.", "transcription": None}
    except Exception as e:
        logger.error(f"Groq Whisper failed: {e}")
        # Return fallback rather than hard error so frontend knows to switch UI
        return {"status": "fallback", "message": "Voice processing failed. Please use buttons.", "transcription": None}

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def ping_db_forever(interval_seconds: int = 240) -> None:
    """Keep Neon pooled connection warm in small deployments."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover
            logger.warning("DB ping failed: %s", exc)
        await asyncio.sleep(interval_seconds)

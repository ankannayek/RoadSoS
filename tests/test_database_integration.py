import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured")


async def test_test_database_has_required_extensions():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'pgcrypto', 'vector')")
            )
            extensions = {row.extname for row in result}
        assert {"postgis", "pgcrypto", "vector"}.issubset(extensions)
    finally:
        await engine.dispose()


async def test_test_database_has_production_hardening_tables():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN ('background_jobs', 'user_private_profiles', 'incident_responder_attempts')
                    """
                )
            )
            tables = {row.table_name for row in result}
        assert {"background_jobs", "user_private_profiles", "incident_responder_attempts"}.issubset(tables)
    finally:
        await engine.dispose()

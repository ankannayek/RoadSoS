from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings


def _connect_args() -> dict:
    if settings.asyncpg_ssl_required:
        return {"ssl": "require"}
    return {}


engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
<<<<<<< HEAD
    pool_timeout=10,
=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
<<<<<<< HEAD
        except Exception:
            await session.rollback()
            raise
=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
        finally:
            await session.close()

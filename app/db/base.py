from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


engine: AsyncEngine | None = None
async_session: async_sessionmaker[AsyncSession] | None = None


def setup_engine(database_url: str) -> None:
    global engine, async_session
    engine = create_async_engine(database_url, echo=False, future=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    from . import models  # noqa: F401  Ensure models are imported for metadata
    assert engine is not None
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

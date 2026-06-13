from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from .config import settings


engine = create_async_engine(settings.async_database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create tables and enable pgvector extension."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Poor-man's migration for columns added after initial deploy
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR")
        )
        await conn.execute(
            text("ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS source VARCHAR")
        )
        await conn.execute(
            text("ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS external_id VARCHAR")
        )

"""Episodic memory store backed by PostgreSQL + pgvector."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import MemoryEpisode
from . import embedding_service


async def store(
    db: AsyncSession,
    user_id: str,
    content: str,
    episode_type: str = "general",
    importance: float = 1.0,
) -> MemoryEpisode:
    embedding = await embedding_service.embed(content)
    episode = MemoryEpisode(
        user_id=user_id,
        content=content,
        episode_type=episode_type,
        embedding=embedding,
        importance=importance,
    )
    db.add(episode)
    await db.commit()
    await db.refresh(episode)
    return episode


async def retrieve(
    db: AsyncSession,
    user_id: str,
    query: str,
    limit: int = 5,
    episode_type: str | None = None,
) -> list[MemoryEpisode]:
    """Return the most semantically relevant memories for a query."""
    query_embedding = await embedding_service.embed(query)

    stmt = (
        select(MemoryEpisode)
        .where(MemoryEpisode.user_id == user_id)
        .where(MemoryEpisode.embedding.isnot(None))
    )
    if episode_type:
        stmt = stmt.where(MemoryEpisode.episode_type == episode_type)

    stmt = stmt.order_by(MemoryEpisode.embedding.cosine_distance(query_embedding)).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_recent(
    db: AsyncSession,
    user_id: str,
    limit: int = 10,
) -> list[MemoryEpisode]:
    stmt = (
        select(MemoryEpisode)
        .where(MemoryEpisode.user_id == user_id)
        .order_by(MemoryEpisode.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

"""Resume chunk persistence and semantic retrieval (pgvector)."""
from __future__ import annotations

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import ResumeChunk
from . import embedding_service, resume_chunker


async def store_chunks(db: AsyncSession, user_id: str, resume_text: str) -> int:
    """Chunk, embed, and persist resume chunks for a user.

    Replaces any existing chunks for the user (idempotent re-upload).
    Returns the number of chunks stored.
    """
    chunks = resume_chunker.chunk_resume(resume_text)
    if not chunks:
        # Still clear stale chunks if the new resume produced none
        await db.execute(delete(ResumeChunk).where(ResumeChunk.user_id == user_id))
        await db.commit()
        return 0

    embeddings = await embedding_service.embed_batch([c["content"] for c in chunks])

    await db.execute(delete(ResumeChunk).where(ResumeChunk.user_id == user_id))
    db.add_all([
        ResumeChunk(
            user_id=user_id,
            content=c["content"],
            section=c["section"],
            chunk_index=c["chunk_index"],
            embedding=emb,
        )
        for c, emb in zip(chunks, embeddings)
    ])
    await db.commit()
    return len(chunks)


async def retrieve_chunks(
    db: AsyncSession,
    user_id: str,
    query: str,
    limit: int = 4,
    threshold: float = 0.85,
) -> list[str]:
    """Return the most query-relevant resume chunks, prefixed with their section.

    Chunks with cosine_distance >= threshold are discarded as irrelevant.
    """
    query_embedding = await embedding_service.embed(query)
    # Safe to inline — values are model-generated floats, not user input
    vec_literal = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"

    # vec_literal is inlined (not bound) — psycopg3 positional params conflict
    # with PostgreSQL's ::vector cast syntax. Safe: model-generated floats only.
    sql = text(f"""
        SELECT content, section
        FROM resume_chunks
        WHERE user_id = :user_id
          AND embedding IS NOT NULL
          AND (embedding <=> '{vec_literal}'::vector) < :threshold
        ORDER BY embedding <=> '{vec_literal}'::vector
        LIMIT :limit
    """)

    result = await db.execute(sql, {
        "user_id": user_id,
        "threshold": threshold,
        "limit": limit,
    })
    return [
        f"[{section or 'Resume'}] {content}"
        for content, section in result.fetchall()
    ]


async def count_chunks(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        text("SELECT COUNT(*) FROM resume_chunks WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    return int(result.scalar() or 0)

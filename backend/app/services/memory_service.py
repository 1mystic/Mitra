"""Episodic memory store backed by PostgreSQL + pgvector.

Retrieval uses a hybrid scoring formula:
  hybrid_score = importance * (0.7 * semantic_similarity + 0.3 * recency_decay)

where:
  semantic_similarity = 1 - cosine_distance  (pgvector <=> operator)
  recency_decay       = 1 / (1 + days_since_created)

Only episodes with cosine_distance < threshold (default 0.75) are returned,
filtering out memories with low semantic relevance to the query.
"""
from __future__ import annotations

from sqlalchemy import select, text
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
    threshold: float = 0.75,
) -> list[str]:
    """Return content strings of the most relevant memories for a query.

    Uses hybrid scoring (semantic + recency + importance). Episodes with
    cosine_distance >= threshold are discarded as irrelevant.
    """
    query_embedding = await embedding_service.embed(query)
    # Safe to inline — generated from model output, not user input
    vec_literal = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"

    type_clause = "AND episode_type = :episode_type" if episode_type else ""

    # vec_literal is inlined (not bound) because psycopg3 converts named params to
    # positional $N, which conflicts with PostgreSQL's ::vector cast syntax.
    # Safe: vec_literal contains only model-generated floats.
    sql = text(f"""
        SELECT content
        FROM memory_episodes
        WHERE user_id = :user_id
          AND embedding IS NOT NULL
          AND (embedding <=> '{vec_literal}'::vector) < :threshold
          {type_clause}
        ORDER BY importance * (
            0.7 * (1.0 - (embedding <=> '{vec_literal}'::vector))
            + 0.3 * (1.0 / (1.0 + EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0))
        ) DESC
        LIMIT :limit
    """)

    params: dict = {
        "user_id": user_id,
        "threshold": threshold,
        "limit": limit,
    }
    if episode_type:
        params["episode_type"] = episode_type

    result = await db.execute(sql, params)
    return [row[0] for row in result.fetchall()]


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


def build_episode(state: dict) -> tuple[str, str, float]:
    """Build a rich episode string from agent state for storage.

    Packs intent, user query, and key extracted facts into a single text block.
    Richer episodes (with gap/roadmap data) get higher importance scores so the
    hybrid retriever surfaces them more readily in future turns.

    Returns (content, episode_type, importance).
    """
    intent = state.get("intent", "general")
    messages = state.get("messages", [])
    user_msg = messages[-1].content if messages else ""
    response = state.get("final_response", "")

    lines = [f"Intent: {intent}", f"Query: {user_msg}"]

    opps = state.get("opportunities", [])
    if opps:
        lines.append(
            "Opportunities found: "
            + ", ".join(f"{o['title']} at {o['company']}" for o in opps[:3])
        )

    gap = state.get("gap_analysis")
    if gap:
        missing_names = [m["skill"] for m in gap.get("missing_skills", [])[:5]]
        lines.append(
            f"Skill match: {gap['match_score'] * 100:.0f}%. "
            f"Gaps: {missing_names}"
        )

    roadmap = state.get("roadmap")
    if roadmap and roadmap.get("summary"):
        lines.append(f"Roadmap: {roadmap['summary']}")

    if response:
        lines.append(f"Response: {response[:400]}")

    content = "\n".join(lines)

    # Scale importance by richness of the interaction
    importance = 1.0
    if gap:
        importance += 0.5
    if roadmap and roadmap.get("steps"):
        importance += 0.5
    if opps:
        importance += 0.3
    importance = min(importance, 3.0)

    return content, intent, importance

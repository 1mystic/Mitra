"""Agent 1: Opportunity Hunter — finds relevant internships / hackathons / fellowships."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import Opportunity
from ..services import embedding_service
from .state import AgentState

# Keywords that signal the user wants freshly-fetched listings rather than cached ones
_LIVE_KEYWORDS = {
    "latest", "recent", "new", "newest", "fresh", "today",
    "just posted", "live", "current openings", "new openings",
}


async def opportunity_hunter_node(state: AgentState, db: AsyncSession) -> dict:
    last_message = state["messages"][-1].content
    message_lower = last_message.lower()

    # When the user asks for fresh results, do a quick live fetch and upsert before searching
    wants_live = any(kw in message_lower for kw in _LIVE_KEYWORDS)
    if wants_live:
        try:
            from ..services.job_fetcher import quick_fetch, ingest_jobs
            live_jobs = await quick_fetch(limit_per_source=3)
            if live_jobs:
                await ingest_jobs(live_jobs)
        except Exception as exc:
            # Live fetch failure is non-fatal — fall through to cached search
            import logging
            logging.getLogger(__name__).warning("Live fetch failed: %s", exc)

    # Build query embedding from message + user skills
    query_text = last_message
    profile = state.get("user_profile")
    if profile and profile.get("skills"):
        top_skills = list(profile["skills"].keys())[:10]
        query_text += " " + " ".join(top_skills)

    query_embedding = await embedding_service.embed(query_text)

    # Semantic search over active opportunities
    stmt = (
        select(Opportunity)
        .where(Opportunity.is_active == True)
        .where(Opportunity.embedding.isnot(None))
        .order_by(Opportunity.embedding.cosine_distance(query_embedding))
        .limit(8)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Fallback: most-recent if no embeddings exist yet
    if not rows:
        stmt2 = (
            select(Opportunity)
            .where(Opportunity.is_active == True)
            .order_by(Opportunity.fetched_at.desc())
            .limit(8)
        )
        result2 = await db.execute(stmt2)
        rows = result2.scalars().all()

    opportunities = [
        {
            "id": o.id,
            "title": o.title,
            "company": o.company,
            "location": o.location or "",
            "required_skills": o.required_skills or [],
            "description": o.description or "",
            "type": o.type,
            "deadline": o.deadline,
            "stipend": o.stipend,
            "url": o.url,
            "source": o.source,
            "fetched_at": o.fetched_at.isoformat() if o.fetched_at else None,
        }
        for o in rows
    ]

    return {"opportunities": opportunities}

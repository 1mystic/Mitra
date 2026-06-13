"""Agent 1: Opportunity Hunter — finds relevant internships / hackathons / fellowships."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import Opportunity, SkillProfile
from ..services import embedding_service
from .state import AgentState


async def opportunity_hunter_node(state: AgentState, db: AsyncSession) -> dict:
    user_id = state["user_id"]
    last_message = state["messages"][-1].content

    # Build query embedding from the user's message + their skill profile
    query_text = last_message
    profile = state.get("user_profile")
    if profile and profile.get("skills"):
        top_skills = list(profile["skills"].keys())[:10]
        query_text += " " + " ".join(top_skills)

    query_embedding = await embedding_service.embed(query_text)

    # Semantic search over stored opportunities
    stmt = (
        select(Opportunity)
        .where(Opportunity.is_active == True)
        .where(Opportunity.embedding.isnot(None))
        .order_by(Opportunity.embedding.cosine_distance(query_embedding))
        .limit(8)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Fallback: if no embeddings yet, return most recent active opportunities
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
            "skills_required": o.required_skills or [],
            "type": o.type,
            "deadline": o.deadline,
            "stipend": o.stipend,
            "url": o.url,
        }
        for o in rows
    ]

    return {"opportunities": opportunities}

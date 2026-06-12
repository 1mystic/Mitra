"""Agent 2: Resume Analyzer — extracts and persists a structured skill profile."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import SkillProfile
from ..services import embedding_service, skill_graph
from .state import AgentState


async def resume_analyzer_node(state: AgentState, db: AsyncSession) -> dict:
    user_id = state["user_id"]

    # Fetch the stored resume text (uploaded via /profile endpoint)
    stmt = select(SkillProfile).where(SkillProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile_row = result.scalar_one_or_none()

    if not profile_row or not profile_row.resume_text:
        return {
            "error": "No resume found. Please upload your resume first via POST /api/profile/upload.",
            "user_profile": None,
        }

    # Re-extract skills (useful when resume was just uploaded)
    extracted = await skill_graph.extract_from_text(profile_row.resume_text)

    # Persist updated profile
    profile_row.skills = extracted["skills"]
    profile_row.projects = extracted["projects"]
    profile_row.experience_text = extracted["experience_summary"]

    # Refresh profile embedding from skills + projects summary
    embed_text = (
        " ".join(extracted["skills"].keys())
        + " "
        + " ".join(p.get("description", "") for p in extracted["projects"])
    )
    profile_row.embedding = await embedding_service.embed(embed_text)

    await db.commit()

    user_profile = {
        "skills": extracted["skills"],
        "projects": extracted["projects"],
        "experience_summary": extracted["experience_summary"],
    }

    return {"user_profile": user_profile}

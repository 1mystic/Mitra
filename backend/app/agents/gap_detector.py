"""Agent 3: Gap Detector — computes skill gaps between user profile and target opportunities."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import GapAnalysis, SkillProfile
from ..services import skill_graph
from .state import AgentState


async def gap_detector_node(state: AgentState, db: AsyncSession) -> dict:
    user_id = state["user_id"]

    # Load user skills
    profile = state.get("user_profile")
    if not profile:
        stmt = select(SkillProfile).where(SkillProfile.user_id == user_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            profile = {"skills": row.skills or {}, "projects": row.projects or []}
        else:
            return {"error": "No skill profile found. Please upload your resume first."}

    candidate_skills: dict = profile.get("skills", {})

    # Aggregate required skills from all fetched opportunities
    opportunities = state.get("opportunities", [])
    if opportunities:
        # Use the best-matched opportunity for gap analysis
        target = opportunities[0]
        required_skills = target.get("required_skills", [])
        context = f"{target['title']} at {target['company']}"
    else:
        # Generic gap analysis against common ML roles
        required_skills = [
            "Python", "PyTorch", "Machine Learning", "Deep Learning",
            "LLMs", "FastAPI", "SQL", "Docker", "Git",
        ]
        context = "ML/AI internship roles in India"

    match_score, present, missing = await skill_graph.compute_match(candidate_skills, required_skills)

    summary_prompt = f"""Summarize this skill gap analysis in 3-4 sentences for a student.

Role context: {context}
Match score: {match_score * 100:.0f}%
Present skills: {present}
Missing skills: {[m['skill'] for m in missing]}

Be encouraging but honest. Focus on the most impactful gaps to close."""

    from ..services import llm_client
    summary = await llm_client.complete(summary_prompt, max_tokens=300)

    gap_result = {
        "match_score": match_score,
        "missing_skills": missing,
        "present_skills": present,
        "summary": summary,
    }

    # Persist to DB
    opportunity_id = opportunities[0]["id"] if opportunities else None
    db.add(GapAnalysis(
        user_id=user_id,
        opportunity_id=opportunity_id,
        match_score=match_score,
        missing_skills=missing,
        present_skills=present,
        summary=summary,
    ))
    await db.commit()

    return {"gap_analysis": gap_result}

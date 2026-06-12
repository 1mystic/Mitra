"""Agent 4: Roadmap Planner — generates a concrete, prioritised learning roadmap."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import Roadmap
from ..services import llm_client
from .state import AgentState


async def roadmap_planner_node(state: AgentState, db: AsyncSession) -> dict:
    user_id = state["user_id"]
    gap = state.get("gap_analysis")
    profile = state.get("user_profile", {})
    opportunities = state.get("opportunities", [])

    if not gap:
        return {"error": "Gap analysis is required before generating a roadmap."}

    missing = gap.get("missing_skills", [])
    if not missing:
        return {
            "roadmap": {
                "steps": [],
                "total_hours": 0,
                "summary": "Great news — you already have all the required skills! Focus on applying now.",
            }
        }

    target_role = ""
    if opportunities:
        target_role = f"{opportunities[0]['title']} at {opportunities[0]['company']}"

    existing_skills = list(profile.get("skills", {}).keys())

    prompt = f"""Create a concrete, actionable learning roadmap for a student.

Target role: {target_role or "ML/AI internship"}
Missing skills (prioritized): {missing}
Student already knows: {existing_skills}

For each skill gap, provide:
- A specific learning step (not generic "study X")
- The best free resource (Coursera course, GitHub repo, paper, YouTube series, Kaggle competition)
- Realistic hours to reach job-ready level

Return JSON:
{{
  "steps": [
    {{
      "step": "Build a recommender system from scratch using Matrix Factorization",
      "resource": "Fast.ai Practical Deep Learning for Coders — Lesson 6",
      "hours": 25,
      "priority": 1,
      "skill": "Recommender Systems"
    }}
  ],
  "total_hours": 85,
  "summary": "2-3 sentence overview of the plan"
}}

Order steps by priority. Be specific about resources."""

    result = await llm_client.complete_json(prompt)

    if not isinstance(result, dict) or "steps" not in result:
        result = {"steps": [], "total_hours": 0, "summary": "Could not generate roadmap."}

    roadmap_data = {
        "steps": result.get("steps", []),
        "total_hours": result.get("total_hours", 0),
        "summary": result.get("summary", ""),
    }

    # Persist
    gap_analysis_id = None  # could link if we had the DB id
    db.add(Roadmap(
        user_id=user_id,
        steps=roadmap_data["steps"],
        total_hours=roadmap_data["total_hours"],
        summary=roadmap_data["summary"],
    ))
    await db.commit()

    return {"roadmap": roadmap_data}

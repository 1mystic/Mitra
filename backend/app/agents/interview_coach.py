"""Agent 6: Interview Coach — generates questions and evaluates answers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import SkillProfile
from ..services import llm_client
from .state import AgentState


async def interview_coach_node(state: AgentState, db: AsyncSession) -> dict:
    user_id = state["user_id"]
    last_message = state["messages"][-1].content
    opportunities = state.get("opportunities", [])

    # Build context: target role + candidate skills
    role_context = ""
    if opportunities:
        o = opportunities[0]
        role_context = f"{o['title']} at {o['company']} — required skills: {', '.join(o.get('required_skills', []))}"
    else:
        role_context = "ML/AI internship"

    stmt = select(SkillProfile).where(SkillProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile_row = result.scalar_one_or_none()
    candidate_skills = list(profile_row.skills.keys()) if profile_row and profile_row.skills else []

    # Detect if the user is answering a previous question
    is_answering = any(kw in last_message.lower() for kw in ("my answer", "i would", "i think", "the answer"))

    if is_answering:
        # Evaluate the answer
        eval_prompt = f"""The candidate is interviewing for: {role_context}
Their skills include: {candidate_skills}

They answered: "{last_message}"

Evaluate this answer on:
1. Technical accuracy (1-5)
2. Depth of explanation (1-5)
3. Communication clarity (1-5)

Provide:
- Score for each dimension
- What was strong
- What could be improved
- A model answer they can learn from

Be constructive and specific."""
        response = await llm_client.complete(eval_prompt, max_tokens=600)
    else:
        # Generate interview questions
        question_prompt = f"""Generate 5 interview questions for: {role_context}
Candidate skill level: {candidate_skills}

Include a mix of:
- 2 technical/coding questions
- 1 system design question (appropriate for internship level)
- 1 project/experience question
- 1 behavioral question

Format each question clearly. After questions, add a brief tip for this specific role."""
        response = await llm_client.complete(question_prompt, max_tokens=800)

    return {"final_response": response}

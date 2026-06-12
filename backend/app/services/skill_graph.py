"""Extract and compare skill graphs from text using Claude."""
from __future__ import annotations

import json

from . import llm_client


_EXTRACT_SYSTEM = """You are a technical recruiter AI. Extract skills from text precisely.
Return valid JSON only, no markdown fences."""

_EXTRACT_PROMPT = """Extract all technical skills mentioned in this text.
For each skill, estimate proficiency on a scale 0.0 (mentioned/basic) to 1.0 (expert).

Return JSON in this exact format:
{{
  "skills": {{"Python": 0.9, "PyTorch": 0.7, "SQL": 0.6}},
  "projects": [
    {{"name": "Project Name", "description": "one-line description", "skills": ["Python", "FastAPI"]}}
  ],
  "experience_summary": "2-3 sentence summary of the person's background"
}}

Text to analyze:
{text}"""


async def extract_from_text(text: str) -> dict:
    """Use Claude to extract a structured skill profile from free-form text (resume, bio)."""
    prompt = _EXTRACT_PROMPT.format(text=text[:4000])
    result = await llm_client.complete_json(prompt, system=_EXTRACT_SYSTEM)
    return {
        "skills": result.get("skills", {}),
        "projects": result.get("projects", []),
        "experience_summary": result.get("experience_summary", ""),
    }


async def compute_match(
    candidate_skills: dict[str, float],
    required_skills: list[str],
) -> tuple[float, list[str], list[dict]]:
    """
    Compare candidate skills against job requirements.

    Returns:
        match_score   - 0.0 to 1.0
        present       - skills the candidate has
        missing       - [{skill, priority, hours}] sorted by priority
    """
    if not required_skills:
        return 1.0, list(candidate_skills.keys()), []

    candidate_lower = {k.lower(): v for k, v in candidate_skills.items()}
    present = []
    missing_raw = []

    for skill in required_skills:
        if skill.lower() in candidate_lower:
            present.append(skill)
        else:
            missing_raw.append(skill)

    match_score = len(present) / len(required_skills) if required_skills else 1.0

    # Ask Claude to prioritize missing skills and estimate effort
    if missing_raw:
        prompt = f"""Given these missing skills for a job application, rank them by importance and estimate learning hours.

Missing skills: {missing_raw}
Job context: requires {required_skills}
Candidate already has: {list(candidate_skills.keys())}

Return JSON array:
[
  {{"skill": "PyTorch", "priority": 1, "hours": 30, "reason": "core requirement"}},
  {{"skill": "GCP", "priority": 2, "hours": 10, "reason": "cloud deployment"}}
]"""
        missing = await llm_client.complete_json(prompt)
        if not isinstance(missing, list):
            missing = [{"skill": s, "priority": i + 1, "hours": 20} for i, s in enumerate(missing_raw)]
    else:
        missing = []

    return round(match_score, 2), present, missing

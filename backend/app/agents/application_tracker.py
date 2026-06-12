"""Agent 5: Application Tracker — manages and summarises the user's application pipeline."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import Application
from ..services import llm_client, memory_service
from .state import AgentState


async def application_tracker_node(state: AgentState, db: AsyncSession) -> dict:
    user_id = state["user_id"]
    last_message = state["messages"][-1].content.lower()

    # Fetch all applications for this user
    stmt = select(Application).where(Application.user_id == user_id).order_by(Application.created_at.desc())
    result = await db.execute(stmt)
    apps = result.scalars().all()

    applications = [
        {
            "id": a.id,
            "company": a.company,
            "role": a.role,
            "status": a.status,
            "applied_date": a.applied_date,
            "deadline": a.deadline,
            "notes": a.notes,
        }
        for a in apps
    ]

    # Check if user wants to log a new application
    if any(kw in last_message for kw in ("applied to", "applied for", "add application", "track application")):
        extract_prompt = f"""The user said: "{state['messages'][-1].content}"

Extract application details if present:
{{
  "company": "...",
  "role": "...",
  "status": "applied",
  "applied_date": "YYYY-MM-DD or null",
  "deadline": "YYYY-MM-DD or null"
}}

If no clear application to add, return null."""
        parsed = await llm_client.complete_json(extract_prompt)
        if isinstance(parsed, dict) and parsed.get("company"):
            new_app = Application(
                user_id=user_id,
                company=parsed.get("company", ""),
                role=parsed.get("role", ""),
                status=parsed.get("status", "applied"),
                applied_date=parsed.get("applied_date"),
                deadline=parsed.get("deadline"),
            )
            db.add(new_app)
            await db.commit()
            # Store in memory
            await memory_service.store(
                db, user_id,
                f"Applied to {new_app.company} for {new_app.role}",
                episode_type="application",
            )
            applications.insert(0, {
                "id": new_app.id,
                "company": new_app.company,
                "role": new_app.role,
                "status": new_app.status,
                "applied_date": new_app.applied_date,
                "deadline": new_app.deadline,
                "notes": None,
            })

    return {"tracked_applications": applications}

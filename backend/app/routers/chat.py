"""
Streaming SSE chat endpoint.

GET  /api/chat/health
POST /api/chat           → non-streaming JSON response
POST /api/chat/stream    → Server-Sent Events (text/event-stream)
"""
from __future__ import annotations

import json
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.graph import build_graph
from ..database import get_db
from ..models.db import SkillProfile, User
from ..models.schemas import ChatRequest, ChatResponse
from ..services import memory_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

# user_id → deque of request timestamps (maxlen=10 enforces sliding window)
_rate_limit: dict[str, deque] = {}


def _enforce_rate_limit(user_id: str) -> None:
    now = time.time()
    bucket = _rate_limit.setdefault(user_id, deque(maxlen=10))
    if len(bucket) == 10 and (now - bucket[0]) < 60:
        raise HTTPException(status_code=429, detail="Rate limit: 10 requests/minute")
    bucket.append(now)


async def _build_initial_state(user_id: str, message: str, db: AsyncSession) -> dict:
    """Populate initial AgentState from DB before graph execution."""
    # Load skill profile if it exists
    res = await db.execute(select(SkillProfile).where(SkillProfile.user_id == user_id))
    profile_row = res.scalar_one_or_none()
    user_profile = None
    if profile_row and profile_row.skills:
        user_profile = {
            "skills": profile_row.skills,
            "projects": profile_row.projects or [],
            "experience_summary": profile_row.experience_text or "",
        }

    return {
        "user_id": user_id,
        "messages": [HumanMessage(content=message)],
        "intent": "",
        "user_profile": user_profile,
        "opportunities": [],
        "gap_analysis": None,
        "roadmap": None,
        "tracked_applications": [],
        "memory_context": [],
        "resume_context": [],
        "final_response": "",
        "error": None,
    }


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Non-streaming chat — returns complete response."""
    # Verify user
    res = await db.execute(select(User).where(User.id == body.user_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    initial_state = await _build_initial_state(body.user_id, body.message, db)
    graph = build_graph(db)
    final_state = await graph.ainvoke(initial_state)

    response_text = final_state.get("final_response") or final_state.get("error") or "I couldn't process that request."

    # Store this interaction in memory
    await memory_service.store(
        db, body.user_id,
        f"User asked: {body.message[:200]} | Mitra replied about: {final_state.get('intent', 'general')}",
        episode_type="general",
        importance=0.6,
    )

    return ChatResponse(
        user_id=body.user_id,
        response=response_text,
        intent=final_state.get("intent"),
        data={
            "opportunities": final_state.get("opportunities", [])[:5],
            "gap_analysis": final_state.get("gap_analysis"),
            "roadmap": final_state.get("roadmap"),
        },
    )


@router.post("/stream")
async def chat_stream(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Streaming SSE endpoint.
    Emits progress events as each agent node completes,
    then streams the final response token-by-token.
    """
    _enforce_rate_limit(body.user_id)
    res = await db.execute(select(User).where(User.id == body.user_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    initial_state = await _build_initial_state(body.user_id, body.message, db)
    graph = build_graph(db)

    async def event_generator():
        accumulated: dict = {**initial_state}
        try:
            async for event in graph.astream(initial_state, stream_mode="updates"):
                node_name = list(event.keys())[0]
                update = event[node_name]

                # Accumulate state updates first so we can annotate progress events
                for k, v in update.items():
                    if k == "messages":
                        accumulated.setdefault("messages", [])
                        if isinstance(v, list):
                            accumulated["messages"] = accumulated["messages"] + v
                    else:
                        accumulated[k] = v

                # Build a richer, contextual progress label
                detail = _progress_detail(node_name, update, accumulated)
                yield f"data: {json.dumps({'type': 'progress', 'node': node_name, 'detail': detail})}\n\n"

                # Emit structured opportunity data immediately when available
                if node_name == "opportunity_hunter" and update.get("opportunities"):
                    opps = update["opportunities"][:6]
                    yield f"data: {json.dumps({'type': 'data', 'key': 'opportunities', 'value': opps})}\n\n"

                # Emit gap data immediately when available
                if node_name == "gap_detector" and update.get("gap_analysis"):
                    gap = update["gap_analysis"]
                    score = gap.get("match_score", 0)
                    yield f"data: {json.dumps({'type': 'data', 'key': 'gap_score', 'value': round(score * 100)})}\n\n"

                # Stream response text once the responder node fires.
                # Read from accumulated state, not the bare update — interview_coach
                # sets final_response on its own node and responder returns {} for it,
                # so update.get("final_response") would be empty in that path.
                if node_name == "responder":
                    text = accumulated.get("final_response", "")
                    if text:
                        words = text.split(" ")
                        for i, word in enumerate(words):
                            chunk = word + (" " if i < len(words) - 1 else "")
                            yield f"data: {json.dumps({'type': 'token', 'chunk': chunk})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _progress_detail(node: str, update: dict, state: dict) -> str:
    """Return a human-readable detail string for a progress event."""
    if node == "memory_retriever":
        n = len(update.get("memory_context") or [])
        return f"Recalled {n} memor{'y' if n == 1 else 'ies'}" if n else "Checking memory…"
    if node == "router":
        return "Ready"
    if node == "intent_router":
        intent = update.get("intent") or state.get("intent") or "general"
        labels = {
            "opportunities": "Searching for internships",
            "resume": "Analysing resume",
            "gaps": "Running gap analysis",
            "roadmap": "Planning roadmap",
            "track": "Checking applications",
            "interview": "Interview coaching",
            "general": "Understanding your question",
        }
        return labels.get(intent, "Routing…")
    if node == "opportunity_hunter":
        n = len(update.get("opportunities") or [])
        return f"Found {n} matching internship{'s' if n != 1 else ''}" if n else "Searching listings…"
    if node == "gap_detector":
        gap = update.get("gap_analysis") or {}
        score = gap.get("match_score")
        if score is not None:
            return f"Skill match: {round(score * 100)}%"
        return "Analysing skill gaps…"
    if node == "roadmap_planner":
        roadmap = update.get("roadmap") or {}
        steps = len(roadmap.get("steps") or [])
        return f"Built {steps}-step roadmap" if steps else "Building roadmap…"
    if node == "resume_analyzer":
        profile = update.get("user_profile") or {}
        skills = len(profile.get("skills") or {})
        return f"Extracted {skills} skills" if skills else "Reading resume…"
    if node == "application_tracker":
        apps = update.get("tracked_applications") or []
        return f"Found {len(apps)} application{'s' if len(apps) != 1 else ''}"
    if node == "interview_coach":
        return "Crafting interview plan…"
    if node == "responder":
        return "Writing response…"
    if node == "memory_writer":
        return "Saving to memory"
    return ""

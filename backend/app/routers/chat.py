"""
Streaming SSE chat endpoint.

GET  /api/chat/health
POST /api/chat           → non-streaming JSON response
POST /api/chat/stream    → Server-Sent Events (text/event-stream)
"""
from __future__ import annotations

import json

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
    res = await db.execute(select(User).where(User.id == body.user_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    initial_state = await _build_initial_state(body.user_id, body.message, db)
    graph = build_graph(db)

    async def event_generator():
        final_state = {}
        try:
            async for event in graph.astream(initial_state, stream_mode="updates"):
                node_name = list(event.keys())[0]
                update = event[node_name]

                # Emit progress notification
                yield f"data: {json.dumps({'type': 'progress', 'node': node_name})}\n\n"

                # Cache final state for post-processing
                final_state.update(update)

                # If the responder just ran, stream the response text
                if node_name == "responder" and update.get("final_response"):
                    text = update["final_response"]
                    # Chunk by word for a streaming feel
                    words = text.split(" ")
                    for i, word in enumerate(words):
                        chunk = word + (" " if i < len(words) - 1 else "")
                        yield f"data: {json.dumps({'type': 'token', 'chunk': chunk})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

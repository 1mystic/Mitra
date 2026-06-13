"""
Mitra LangGraph multi-agent orchestration.

Flow:
  START
    → memory_retriever      (inject relevant memories into state)
    → intent_router         (classify intent, route to sub-agent)
    ↓
  [opportunity_hunter] → gap_detector → roadmap_planner → responder → END
  [resume_analyzer]                                      → responder → END
  [gaps]               → gap_detector → roadmap_planner → responder → END
  [roadmap]                            → roadmap_planner → responder → END
  [application_tracker]                                  → responder → END
  [interview_coach]                                      → END (sets final_response itself)
  [general]                                              → responder → END
"""
from __future__ import annotations

from functools import partial
from typing import Callable

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from ..services import llm_client, memory_service, resume_service
from .application_tracker import application_tracker_node
from .gap_detector import gap_detector_node
from .interview_coach import interview_coach_node
from .opportunity_hunter import opportunity_hunter_node
from .resume_analyzer import resume_analyzer_node
from .roadmap_planner import roadmap_planner_node
from .state import AgentState


# ── Utility: inject DB session into node functions ────────────────────────────

def _bind_db(fn: Callable, db: AsyncSession) -> Callable:
    """Return a wrapped node that passes `db` as keyword arg."""
    async def wrapped(state: AgentState) -> dict:
        return await fn(state, db=db)
    wrapped.__name__ = fn.__name__
    return wrapped


# ── Core nodes ────────────────────────────────────────────────────────────────

async def memory_retriever_node(state: AgentState, db: AsyncSession) -> dict:
    """Retrieve relevant episodic memories and resume chunks before routing."""
    user_id = state["user_id"]
    query = state["messages"][-1].content
    memory_context = await memory_service.retrieve(db, user_id, query, limit=5)
    resume_context = await resume_service.retrieve_chunks(db, user_id, query, limit=4)
    return {"memory_context": memory_context, "resume_context": resume_context}


async def intent_router_node(state: AgentState) -> dict:
    """Classify the user's intent to route to the correct sub-agent."""
    message = state["messages"][-1].content
    intent = await llm_client.classify_intent(message)
    return {"intent": intent}


def route_intent(state: AgentState) -> str:
    return state.get("intent", "general")


async def memory_writer_node(state: AgentState, db: AsyncSession) -> dict:
    """Persist the completed conversation turn as an episodic memory episode."""
    user_id = state["user_id"]
    content, episode_type, importance = memory_service.build_episode(state)
    await memory_service.store(db, user_id, content, episode_type=episode_type, importance=importance)
    # LangGraph requires at least one known key in every node return
    return {"error": None}


async def responder_node(state: AgentState) -> dict:
    """
    Final synthesis node: generates a response given all accumulated state.
    Called by all paths except interview_coach (which writes final_response directly).
    """
    if state.get("final_response"):
        return {}  # interview_coach already set it

    user_message = state["messages"][-1].content
    intent = state.get("intent", "general")
    memory_ctx = state.get("memory_context", [])

    # Build a rich context string
    ctx_parts: list[str] = []

    if memory_ctx:
        ctx_parts.append("Relevant memory:\n" + "\n".join(f"- {m}" for m in memory_ctx))

    resume_ctx = state.get("resume_context", [])
    if resume_ctx:
        ctx_parts.append("Relevant resume excerpts:\n" + "\n".join(f"- {c}" for c in resume_ctx))

    profile = state.get("user_profile")
    if profile:
        skills = list(profile.get("skills", {}).keys())[:10]
        ctx_parts.append(f"User skills: {', '.join(skills)}")

    opps = state.get("opportunities", [])
    if opps:
        opp_lines = [f"- {o['title']} at {o['company']} ({o['type']})" for o in opps[:5]]
        ctx_parts.append("Matched opportunities:\n" + "\n".join(opp_lines))

    gap = state.get("gap_analysis")
    if gap:
        ctx_parts.append(
            f"Skill gap: {gap['match_score']*100:.0f}% match. "
            f"Missing: {[m['skill'] for m in gap.get('missing_skills', [])]}"
        )

    roadmap = state.get("roadmap")
    if roadmap and roadmap.get("steps"):
        steps = roadmap["steps"][:5]
        step_lines = [f"{i+1}. {s['step']} (~{s['hours']}h) — {s['resource']}" for i, s in enumerate(steps)]
        ctx_parts.append("Learning roadmap:\n" + "\n".join(step_lines))
        if roadmap.get("summary"):
            ctx_parts.append(f"Roadmap summary: {roadmap['summary']}")

    tracked = state.get("tracked_applications", [])
    if tracked:
        status_counts: dict[str, int] = {}
        for a in tracked:
            status_counts[a["status"]] = status_counts.get(a["status"], 0) + 1
        ctx_parts.append(f"Applications: {dict(status_counts)}")

    context_block = "\n\n".join(ctx_parts)

    system = """You are Mitra, an AI Career Intelligence OS for students seeking ML/AI internships.
You are direct, encouraging, and technically precise. You never give vague advice.
Always ground your response in the specific data you have about the student."""

    prompt = f"""Context about this student:
{context_block}

Student's message: {user_message}

Respond helpfully and concisely. If you found opportunities, list the top 3 with key details.
If you computed a skill gap, lead with the match score and the top 3 priorities.
If you built a roadmap, show the first 3 steps clearly."""

    response = await llm_client.complete(prompt, system=system, max_tokens=1000)
    return {"final_response": response, "messages": [AIMessage(content=response)]}


# ── Graph factory ─────────────────────────────────────────────────────────────

def build_graph(db: AsyncSession) -> "CompiledGraph":
    """Build and compile the Mitra agent graph, binding the DB session."""
    builder = StateGraph(AgentState)

    # Register nodes (all bound to the DB session for this request)
    builder.add_node("memory_retriever",    _bind_db(memory_retriever_node, db))
    builder.add_node("intent_router",       intent_router_node)
    builder.add_node("opportunity_hunter",  _bind_db(opportunity_hunter_node, db))
    builder.add_node("resume_analyzer",     _bind_db(resume_analyzer_node, db))
    builder.add_node("gap_detector",        _bind_db(gap_detector_node, db))
    builder.add_node("roadmap_planner",     _bind_db(roadmap_planner_node, db))
    builder.add_node("application_tracker", _bind_db(application_tracker_node, db))
    builder.add_node("interview_coach",     _bind_db(interview_coach_node, db))
    builder.add_node("responder",           responder_node)
    builder.add_node("memory_writer",       _bind_db(memory_writer_node, db))

    # Entry
    builder.add_edge(START, "memory_retriever")
    builder.add_edge("memory_retriever", "intent_router")

    # Route by intent
    builder.add_conditional_edges(
        "intent_router",
        route_intent,
        {
            "opportunities": "opportunity_hunter",
            "resume":        "resume_analyzer",
            "gaps":          "gap_detector",
            "roadmap":       "roadmap_planner",
            "track":         "application_tracker",
            "interview":     "interview_coach",
            "general":       "responder",
        },
    )

    # Sub-agent chains
    builder.add_edge("opportunity_hunter",  "gap_detector")
    builder.add_edge("gap_detector",        "roadmap_planner")
    builder.add_edge("roadmap_planner",     "responder")
    builder.add_edge("resume_analyzer",     "responder")
    builder.add_edge("application_tracker", "responder")
    builder.add_edge("interview_coach",     "responder")
    builder.add_edge("responder",           "memory_writer")
    builder.add_edge("memory_writer",       END)

    return builder.compile()

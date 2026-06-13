"""Shared LangGraph state definition for Mitra's multi-agent graph."""
from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Core conversation
    user_id: str
    messages: Annotated[list[BaseMessage], add_messages]

    # Routing
    intent: str   # opportunities | resume | gaps | roadmap | track | interview | general

    # Agent outputs (accumulated across steps)
    user_profile: Optional[dict]        # {skills, projects, experience_summary}
    opportunities: list[dict]           # list of matched opportunities
    gap_analysis: Optional[dict]        # {match_score, missing_skills, present_skills, summary}
    roadmap: Optional[dict]             # {steps, total_hours, summary}
    tracked_applications: list[dict]    # application records

    # Memory context injected at graph entry
    memory_context: list[str]

    # Relevant resume chunks (RAG) injected at graph entry
    resume_context: list[str]

    # Final streamed response (set by responder node)
    final_response: str

    # Error propagation
    error: Optional[str]

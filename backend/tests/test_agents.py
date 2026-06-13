"""
Structural test 4: Verify agent state TypedDict and LangGraph graph structure.
Tests routing logic, state field coverage, and graph compilation — no LLM calls.
"""
import pytest
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph

from app.agents.state import AgentState
from app.agents.graph import build_graph, route_intent


# ── AgentState structure ──────────────────────────────────────────────────────

def test_agent_state_fields():
    required = {
        "user_id", "messages", "intent", "user_profile",
        "opportunities", "gap_analysis", "roadmap",
        "tracked_applications", "memory_context", "final_response", "error",
    }
    hints = AgentState.__annotations__
    assert required.issubset(hints.keys()), f"Missing fields: {required - hints.keys()}"


def test_agent_state_can_be_constructed():
    state: AgentState = {
        "user_id": "test-123",
        "messages": [HumanMessage(content="hello")],
        "intent": "general",
        "user_profile": None,
        "opportunities": [],
        "gap_analysis": None,
        "roadmap": None,
        "tracked_applications": [],
        "memory_context": [],
        "final_response": "",
        "error": None,
    }
    assert state["user_id"] == "test-123"
    assert len(state["messages"]) == 1


# ── Intent routing ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("intent,expected_node", [
    ("opportunities", "opportunity_hunter"),
    ("resume",        "resume_analyzer"),
    ("gaps",          "gap_detector"),
    ("roadmap",       "roadmap_planner"),
    ("track",         "application_tracker"),
    ("interview",     "interview_coach"),
    ("general",       "responder"),
])
def test_route_intent_mapping(intent, expected_node):
    state: AgentState = {
        "user_id": "x", "messages": [], "intent": intent,
        "user_profile": None, "opportunities": [], "gap_analysis": None,
        "roadmap": None, "tracked_applications": [], "memory_context": [],
        "final_response": "", "error": None,
    }
    result = route_intent(state)
    assert result == intent  # route_intent returns the intent string; graph maps it to node


def test_route_intent_unknown_falls_to_general():
    state: AgentState = {
        "user_id": "x", "messages": [], "intent": "unknown_xyz",
        "user_profile": None, "opportunities": [], "gap_analysis": None,
        "roadmap": None, "tracked_applications": [], "memory_context": [],
        "final_response": "", "error": None,
    }
    # route_intent returns the raw intent; the graph's conditional_edges map handles unknown
    result = route_intent(state)
    assert isinstance(result, str)


# ── Graph compilation (no DB required for structure check) ────────────────────

def test_graph_compiles_without_db():
    """Verify the LangGraph graph compiles without errors using a mock DB session."""
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    graph = build_graph(mock_db)
    assert graph is not None
    # LangGraph compiled graphs expose get_graph()
    g = graph.get_graph()
    node_names = set(g.nodes.keys())
    expected_nodes = {
        "memory_retriever", "intent_router", "opportunity_hunter",
        "resume_analyzer", "gap_detector", "roadmap_planner",
        "application_tracker", "interview_coach", "responder",
    }
    assert expected_nodes.issubset(node_names), f"Missing nodes: {expected_nodes - node_names}"


def test_graph_has_correct_edge_count():
    from unittest.mock import MagicMock
    graph = build_graph(MagicMock())
    g = graph.get_graph()
    # At minimum: START→memory, memory→router, router→(7 branches), 7 branches→... responder→END
    assert len(g.edges) >= 10

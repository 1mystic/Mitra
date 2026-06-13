"""
Structural test 1: Verify every module in the project imports without errors.
These tests catch circular imports, missing __init__.py, and bad top-level code.
"""


def test_config_imports():
    from app.config import settings
    assert settings.claude_model
    assert settings.embedding_dim == 384


def test_database_imports():
    from app.database import Base, get_db, init_db
    assert Base is not None


def test_models_db_imports():
    from app.models.db import (
        Application, GapAnalysis, MemoryEpisode,
        Opportunity, Roadmap, SkillProfile, User,
    )


def test_models_schemas_imports():
    from app.models.schemas import (
        ApplicationCreate, ApplicationRead, ApplicationUpdate,
        ChatRequest, ChatResponse, GapAnalysisRead,
        OpportunityCreate, OpportunityRead,
        RoadmapRead, SkillProfileRead,
        UserCreate, UserRead, UserUpdate,
    )


def test_services_imports():
    from app.services import (
        embedding_service, llm_client, memory_service, skill_graph,
    )


def test_agents_imports():
    from app.agents.state import AgentState
    from app.agents import (
        application_tracker, gap_detector, interview_coach,
        opportunity_hunter, resume_analyzer, roadmap_planner,
    )
    from app.agents.graph import build_graph


def test_routers_imports():
    from app.routers import chat, opportunities, profile, tracker, users


def test_main_imports():
    from app.main import app
    assert app.title == "Mitra — Career Intelligence OS"

"""
Structural test 3: Verify Pydantic schemas validate and serialize correctly.
No DB or LLM calls — pure in-process validation.
"""
import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ApplicationCreate, ApplicationUpdate,
    ChatRequest, GapAnalysisRead, MissingSkill,
    OpportunityCreate, RoadmapStep,
    UserCreate, UserUpdate,
)


# ── UserCreate ────────────────────────────────────────────────────────────────

def test_user_create_minimal():
    u = UserCreate()
    assert u.name is None
    assert u.goal is None


def test_user_create_full():
    u = UserCreate(name="Athar", email="a@iitm.ac.in", goal="ML internships", target_role="ML Engineer")
    assert u.name == "Athar"
    assert u.target_role == "ML Engineer"


def test_user_update_partial():
    u = UserUpdate(goal="AI research")
    assert u.goal == "AI research"
    assert u.name is None


# ── ApplicationCreate ─────────────────────────────────────────────────────────

def test_application_create_defaults():
    a = ApplicationCreate(company="Sarvam", role="ML Intern")
    assert a.status == "applied"
    assert a.notes is None


def test_application_create_full():
    a = ApplicationCreate(
        company="Krutrim", role="AI Research Intern",
        status="interview", applied_date="2026-06-01", deadline="2026-08-15",
    )
    assert a.status == "interview"


def test_application_update_partial():
    u = ApplicationUpdate(status="offered")
    assert u.status == "offered"
    assert u.notes is None


# ── OpportunityCreate ─────────────────────────────────────────────────────────

def test_opportunity_create_defaults():
    o = OpportunityCreate(title="ML Intern", company="Sarvam AI")
    assert o.type == "internship"
    assert o.required_skills == []


def test_opportunity_create_with_skills():
    o = OpportunityCreate(
        title="LLM Intern", company="Krutrim",
        required_skills=["Python", "PyTorch", "LLMs"],
        type="internship",
    )
    assert len(o.required_skills) == 3


# ── ChatRequest ───────────────────────────────────────────────────────────────

def test_chat_request_valid():
    r = ChatRequest(user_id="abc", message="Find me ML internships")
    assert r.stream is True


def test_chat_request_no_stream():
    r = ChatRequest(user_id="abc", message="hello", stream=False)
    assert r.stream is False


def test_chat_request_requires_user_id():
    with pytest.raises(ValidationError):
        ChatRequest(message="hello")  # missing user_id


# ── MissingSkill / RoadmapStep ────────────────────────────────────────────────

def test_missing_skill_schema():
    ms = MissingSkill(skill="PyTorch", priority=1, hours=40)
    assert ms.skill == "PyTorch"
    assert ms.priority == 1


def test_roadmap_step_schema():
    rs = RoadmapStep(
        step="Build a recommender system",
        resource="Fast.ai Lesson 6",
        hours=25,
        priority=1,
    )
    assert rs.hours == 25

from __future__ import annotations

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ── Users ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    goal: Optional[str] = None
    target_role: Optional[str] = None


class UserRead(BaseModel):
    id: str
    name: Optional[str]
    email: Optional[str]
    goal: Optional[str]
    target_role: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    target_role: Optional[str] = None


# ── Skill Profile ─────────────────────────────────────────────────────────────

class SkillProfileRead(BaseModel):
    id: str
    user_id: str
    skills: dict
    projects: list
    experience_text: Optional[str]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ProfileUploadResponse(SkillProfileRead):
    """Returned by POST /api/profile/upload — adds chunking metadata."""
    chunk_count: int = 0


# ── Opportunities ─────────────────────────────────────────────────────────────

class OpportunityRead(BaseModel):
    id: str
    title: str
    company: str
    location: Optional[str]
    description: Optional[str]
    required_skills: list[str] = Field(default_factory=list)
    url: Optional[str]
    deadline: Optional[str]
    type: str
    stipend: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class OpportunityCreate(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    url: Optional[str] = None
    deadline: Optional[str] = None
    type: str = "internship"
    stipend: Optional[str] = None


# ── Gap Analysis ──────────────────────────────────────────────────────────────

class MissingSkill(BaseModel):
    skill: str
    priority: int    # 1 = highest
    hours: int       # estimated hours to learn


class GapAnalysisRead(BaseModel):
    id: str
    user_id: str
    opportunity_id: Optional[str]
    match_score: float
    missing_skills: list[MissingSkill]
    present_skills: list[str]
    summary: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Roadmap ───────────────────────────────────────────────────────────────────

class RoadmapStep(BaseModel):
    step: str
    resource: str
    hours: int
    priority: int


class RoadmapRead(BaseModel):
    id: str
    user_id: str
    steps: list[RoadmapStep]
    total_hours: float
    summary: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Application Tracker ───────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    user_id: str
    company: str
    role: str
    status: str = "applied"
    applied_date: Optional[str] = None
    deadline: Optional[str] = None
    notes: Optional[str] = None
    url: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    deadline: Optional[str] = None


class ApplicationRead(BaseModel):
    id: str
    user_id: str
    company: str
    role: str
    status: str
    applied_date: Optional[str]
    deadline: Optional[str]
    notes: Optional[str]
    url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    goal: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserRead"


# ── Chat History ─────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    user_id: str
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: str


class ChatHistoryMessageCreate(BaseModel):
    conversation_id: str
    role: str       # "user" | "assistant"
    content: str


class ChatHistoryMessageRead(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationRead(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationWithMessages(ConversationRead):
    messages: list[ChatHistoryMessageRead] = []


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    user_id: str
    message: str
    stream: bool = True


class ChatResponse(BaseModel):
    user_id: str
    response: str
    intent: Optional[str] = None
    data: Optional[dict] = None

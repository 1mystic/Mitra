import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, JSON,
)
from sqlalchemy.orm import relationship

from ..database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True)
    goal = Column(String, nullable=True)          # e.g. "ML internships in India"
    target_role = Column(String, nullable=True)   # e.g. "ML Engineer"
    created_at = Column(DateTime, default=datetime.utcnow)

    skill_profile = relationship("SkillProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    memory_episodes = relationship("MemoryEpisode", back_populates="user", cascade="all, delete-orphan")


class SkillProfile(Base):
    __tablename__ = "skill_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    skills = Column(JSON, default=dict)        # {"Python": 0.9, "PyTorch": 0.7, ...}
    projects = Column(JSON, default=list)      # [{"name": "...", "description": "..."}]
    experience_text = Column(Text, nullable=True)
    resume_text = Column(Text, nullable=True)
    embedding = Column(Vector(384), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="skill_profile")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    required_skills = Column(JSON, default=list)   # ["Python", "PyTorch", ...]
    url = Column(String, nullable=True)
    deadline = Column(String, nullable=True)
    type = Column(String, default="internship")    # internship | hackathon | fellowship | research
    stipend = Column(String, nullable=True)
    embedding = Column(Vector(384), nullable=True)
    is_active = Column(Boolean, default=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class GapAnalysis(Base):
    __tablename__ = "gap_analyses"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    opportunity_id = Column(String, ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True)
    match_score = Column(Float, nullable=False)
    missing_skills = Column(JSON, default=list)   # [{"skill": "...", "priority": 1, "hours": 20}]
    present_skills = Column(JSON, default=list)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gap_analysis_id = Column(String, ForeignKey("gap_analyses.id", ondelete="SET NULL"), nullable=True)
    steps = Column(JSON, default=list)   # [{"step": "...", "resource": "...", "hours": 10, "priority": 1}]
    total_hours = Column(Float, default=0.0)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    status = Column(String, default="applied")   # applied | interview | offered | rejected
    applied_date = Column(String, nullable=True)
    deadline = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="applications")


class MemoryEpisode(Base):
    __tablename__ = "memory_episodes"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    episode_type = Column(String, default="general")   # goal | skill | application | insight | general
    embedding = Column(Vector(384), nullable=True)
    importance = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="memory_episodes")

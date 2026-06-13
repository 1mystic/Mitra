"""Shared dataclass for all fetched jobs before DB upsert."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FetchedJob:
    title: str
    company: str
    source: str           # "internshala" | "unstop" | "adzuna"
    external_id: str      # source-specific stable ID for upsert dedup
    url: str
    location: Optional[str] = None
    description: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    stipend: Optional[str] = None
    deadline: Optional[str] = None    # YYYY-MM-DD or None
    job_type: str = "internship"

    @property
    def embed_text(self) -> str:
        """Canonical text used to generate the pgvector embedding."""
        parts = [self.title, self.company]
        if self.location:
            parts.append(self.location)
        if self.description:
            parts.append(self.description[:400])
        if self.skills:
            parts.append("Skills: " + ", ".join(self.skills))
        return " | ".join(filter(None, parts))

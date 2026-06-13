"""Remotive remote job fetcher — free public API, no auth required.

Endpoint: https://remotive.com/api/remote-jobs
Categories: software-dev, data, devops, product, design.
Rate limit: max 4 requests/day per IP — we fetch one category per cycle.
"""
from __future__ import annotations

import logging

import httpx

from .normalizer import FetchedJob

logger = logging.getLogger(__name__)

_API = "https://remotive.com/api/remote-jobs"

# Only ML/AI-relevant categories; keep request count minimal given 4/day limit
_CATEGORIES = ["software-dev", "data"]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MitraBot/1.0)",
    "Accept": "application/json",
}

_ML_KEYWORDS = {
    "machine learning", "deep learning", "data science", "nlp",
    "computer vision", "artificial intelligence", "ml engineer",
    "pytorch", "tensorflow", "llm", "intern",
}


async def fetch() -> list[FetchedJob]:
    jobs: list[FetchedJob] = []
    seen: set[str] = set()

    async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
        for cat in _CATEGORIES:
            try:
                r = await client.get(_API, params={"category": cat})
                if r.status_code != 200:
                    logger.warning("Remotive category '%s' returned %d", cat, r.status_code)
                    continue

                data = r.json()
                items = data.get("jobs", [])
                for item in items:
                    # Filter for ML/AI relevance
                    text_blob = " ".join([
                        (item.get("title") or ""),
                        (item.get("description") or ""),
                        " ".join(item.get("tags") or []),
                    ]).lower()

                    if not any(kw in text_blob for kw in _ML_KEYWORDS):
                        continue

                    job = _parse(item)
                    if job and job.external_id not in seen:
                        seen.add(job.external_id)
                        jobs.append(job)

            except Exception as exc:
                logger.warning("Remotive category '%s' failed: %s", cat, exc)

    return jobs


def _parse(item: dict) -> FetchedJob | None:
    try:
        job_id = str(item.get("id", "")).strip()
        title = (item.get("title") or "").strip()
        if not job_id or not title:
            return None

        company = (item.get("company_name") or "").strip()
        if not company:
            return None

        url = (item.get("url") or "").strip()
        if not url:
            return None

        # candidate_required_location tells us geography restrictions
        location_raw = (item.get("candidate_required_location") or "Worldwide").strip()
        # Normalise: "India" / "Worldwide" / "Asia" etc.
        location = location_raw if location_raw else "Remote (Worldwide)"

        tags: list[str] = [t for t in (item.get("tags") or []) if isinstance(t, str) and t][:8]

        salary = (item.get("salary") or "").strip() or None

        desc = (item.get("description") or "")
        # Strip HTML tags roughly
        import re
        desc = re.sub(r"<[^>]+>", " ", desc).strip()[:400]
        if not desc:
            desc = f"{title} at {company}. {location}."

        return FetchedJob(
            title=title,
            company=company,
            source="remotive",
            external_id=f"rm_{job_id}",
            url=url,
            location=f"Remote — {location}" if "remote" not in location.lower() else location,
            description=desc,
            skills=tags,
            stipend=salary,
            deadline=None,
            job_type="internship",
        )
    except Exception:
        return None

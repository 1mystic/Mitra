"""Adzuna Jobs API fetcher — free tier, 250 req/day, India-filtered ML/AI roles.

Sign up at https://developer.adzuna.com/ to get APP_ID and APP_KEY.
Set ADZUNA_APP_ID and ADZUNA_APP_KEY in your .env file.
Without keys this fetcher silently returns [] so the rest of the pipeline still works.
"""
from __future__ import annotations

import logging

import httpx

from ...config import settings
from .normalizer import FetchedJob

logger = logging.getLogger(__name__)

_BASE = "https://api.adzuna.com/v1/api/jobs/in/search"

# Focused queries that map well to ML/AI internship listings on Adzuna India
_QUERIES = [
    "machine learning intern",
    "deep learning intern",
    "data science intern",
    "AI research intern",
    "NLP intern",
    "computer vision intern",
    "MLOps intern",
    "data analyst intern",
]


async def fetch() -> list[FetchedJob]:
    app_id = getattr(settings, "adzuna_app_id", "")
    app_key = getattr(settings, "adzuna_app_key", "")
    if not app_id or not app_key:
        logger.debug("Adzuna keys not configured — skipping")
        return []

    jobs: list[FetchedJob] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for query in _QUERIES:
            try:
                r = await client.get(
                    f"{_BASE}/1",
                    params={
                        "app_id": app_id,
                        "app_key": app_key,
                        "what": query,
                        "results_per_page": 20,
                        "sort_by": "date",
                        "content-type": "application/json",
                    },
                )
                r.raise_for_status()
                for item in r.json().get("results", []):
                    ext_id = str(item.get("id", ""))
                    if not ext_id:
                        continue
                    jobs.append(FetchedJob(
                        title=item.get("title", "").strip(),
                        company=item.get("company", {}).get("display_name", "").strip(),
                        source="adzuna",
                        external_id=f"az_{ext_id}",
                        url=item.get("redirect_url", ""),
                        location=item.get("location", {}).get("display_name", ""),
                        description=(item.get("description") or "")[:600],
                        skills=[],
                        stipend=_fmt_salary(item),
                        deadline=None,
                        job_type="internship",
                    ))
            except Exception as exc:
                logger.warning("Adzuna query '%s' failed: %s", query, exc)

    return _dedup(jobs)


def _fmt_salary(item: dict) -> str | None:
    lo = item.get("salary_min")
    hi = item.get("salary_max")
    if lo and hi and lo != hi:
        return f"₹{int(lo):,}–{int(hi):,}/mo"
    if lo:
        return f"₹{int(lo):,}+/mo"
    return None


def _dedup(jobs: list[FetchedJob]) -> list[FetchedJob]:
    seen: set[str] = set()
    out = []
    for j in jobs:
        if j.external_id not in seen and j.title and j.company:
            seen.add(j.external_id)
            out.append(j)
    return out

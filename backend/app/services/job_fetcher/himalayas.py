"""Himalayas remote job fetcher — free public API, no auth required.

Endpoint: https://himalayas.app/jobs/api
Returns remote/global tech roles. Useful for international remote internships.
Rate-limited to ~100 req/hr; we call once per category per refresh cycle.
"""
from __future__ import annotations

import logging

import httpx

from .normalizer import FetchedJob

logger = logging.getLogger(__name__)

_API = "https://himalayas.app/jobs/api"

_QUERIES = [
    "machine learning intern",
    "data science intern",
    "AI intern",
    "NLP intern",
    "computer vision intern",
    "deep learning intern",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MitraBot/1.0)",
    "Accept": "application/json",
}


async def fetch() -> list[FetchedJob]:
    jobs: list[FetchedJob] = []
    seen: set[str] = set()

    async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
        for query in _QUERIES:
            try:
                r = await client.get(_API, params={"q": query, "limit": 20, "offset": 0})
                if r.status_code != 200:
                    logger.warning("Himalayas query '%s' returned %d", query, r.status_code)
                    continue

                data = r.json()
                items = data.get("jobs", [])
                for item in items:
                    job = _parse(item)
                    if job and job.external_id not in seen:
                        seen.add(job.external_id)
                        jobs.append(job)

            except Exception as exc:
                logger.warning("Himalayas query '%s' failed: %s", query, exc)

    return jobs


def _parse(item: dict) -> FetchedJob | None:
    try:
        job_id = item.get("slug") or str(item.get("id", ""))
        title = (item.get("title") or "").strip()
        if not job_id or not title:
            return None

        company = (
            item.get("companyName")
            or (item.get("company") or {}).get("name")
            or ""
        ).strip()
        if not company:
            return None

        url = item.get("url") or item.get("applicationUrl") or f"https://himalayas.app/jobs/{job_id}"

        # Location: Himalayas is remote-first; timezone restrictions in the data
        timezones = item.get("timezones") or []
        if any("india" in (tz or "").lower() or "asia" in (tz or "").lower() for tz in timezones):
            location = "Remote (India/Asia)"
        else:
            location = "Remote (Worldwide)"

        # Skills from categories + seniority tags
        skills: list[str] = []
        for cat in (item.get("categories") or []):
            name = (cat.get("name") or cat) if isinstance(cat, dict) else str(cat)
            if name:
                skills.append(name)

        # Stipend/salary
        salary_min = item.get("salaryMin") or item.get("salary_min")
        salary_max = item.get("salaryMax") or item.get("salary_max")
        currency = item.get("salaryCurrency") or "USD"
        stipend = None
        if salary_min and salary_max:
            stipend = f"{currency} {int(salary_min):,}–{int(salary_max):,}/yr"
        elif salary_min:
            stipend = f"{currency} {int(salary_min):,}+/yr"

        pub_date = item.get("pubDate") or item.get("publishedAt")
        desc = (item.get("description") or "")[:400] or f"{title} at {company}. {location}."

        return FetchedJob(
            title=title,
            company=company,
            source="himalayas",
            external_id=f"hm_{job_id}",
            url=url,
            location=location,
            description=desc,
            skills=skills[:8],
            stipend=stipend,
            deadline=None,
            job_type="internship",
        )
    except Exception:
        return None

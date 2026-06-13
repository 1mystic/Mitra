"""Unstop public API fetcher — internships + competitions for ML/AI domains.

Unstop exposes a public search endpoint used by their own frontend.
No authentication required. Returns structured JSON.
"""
from __future__ import annotations

import logging

import httpx

from .normalizer import FetchedJob

logger = logging.getLogger(__name__)

_API = "https://unstop.com/api/public/opportunity/search-result"

_DOMAINS = [
    "Machine Learning",
    "Data Science",
    "Artificial Intelligence",
    "Computer Vision",
    "Natural Language Processing",
    "Data Analytics",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://unstop.com/",
    "Origin": "https://unstop.com",
}


async def fetch() -> list[FetchedJob]:
    jobs: list[FetchedJob] = []
    async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
        for domain in _DOMAINS:
            try:
                r = await client.get(
                    _API,
                    params={
                        "opportunity": "internship",
                        "page": 1,
                        "per_page": 25,
                        "domain": domain,
                    },
                )
                if r.status_code != 200:
                    logger.warning("Unstop domain '%s' returned %d", domain, r.status_code)
                    continue

                data = r.json()
                # API returns data.data (list) or data.data.data depending on version
                raw = data.get("data") or {}
                items = raw.get("data", raw) if isinstance(raw, dict) else raw
                if not isinstance(items, list):
                    continue

                for item in items:
                    job = _parse_item(item)
                    if job:
                        jobs.append(job)

            except Exception as exc:
                logger.warning("Unstop domain '%s' failed: %s", domain, exc)

    return _dedup(jobs)


def _parse_item(item: dict) -> FetchedJob | None:
    try:
        opp_id = item.get("id")
        title = (item.get("title") or "").strip()
        if not opp_id or not title:
            return None

        org = item.get("organisation") or {}
        company = (org.get("name") or "").strip()
        if not company:
            return None

        slug = item.get("public_url") or str(opp_id)
        url = f"https://unstop.com/internships/{slug}"

        desc_raw = item.get("description") or item.get("short_description") or ""
        description = desc_raw[:500] if desc_raw else None

        end_date = item.get("end_date") or item.get("application_deadline") or ""
        deadline = end_date[:10] if end_date else None

        return FetchedJob(
            title=title,
            company=company,
            source="unstop",
            external_id=f"un_{opp_id}",
            url=url,
            location=item.get("location_name") or item.get("city") or "India",
            description=description,
            skills=_extract_skills(item),
            stipend=_fmt_stipend(item),
            deadline=deadline,
            job_type="internship",
        )
    except Exception:
        return None


def _extract_skills(item: dict) -> list[str]:
    tags = item.get("tags") or item.get("skills") or []
    return [
        t.get("value") or t.get("name") or ""
        for t in tags
        if isinstance(t, dict) and (t.get("value") or t.get("name"))
    ][:8]


def _fmt_stipend(item: dict) -> str | None:
    lo = item.get("min_stipend") or item.get("stipend_min")
    hi = item.get("max_stipend") or item.get("stipend_max")
    if lo and hi and lo != hi:
        return f"₹{int(lo):,}–{int(hi):,}/mo"
    if lo:
        return f"₹{int(lo):,}+/mo"
    return None


def _dedup(jobs: list[FetchedJob]) -> list[FetchedJob]:
    seen: set[str] = set()
    out = []
    for j in jobs:
        if j.external_id not in seen:
            seen.add(j.external_id)
            out.append(j)
    return out

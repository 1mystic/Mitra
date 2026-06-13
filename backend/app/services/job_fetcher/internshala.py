"""Internshala scraper — highest-volume India internship portal.

Uses httpx + BeautifulSoup. Adds a polite 1.5s delay between category pages.
Fetches 6 ML/AI categories. Respects robots.txt intent by not flooding requests.
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from .normalizer import FetchedJob

logger = logging.getLogger(__name__)

_CATEGORIES = [
    ("machine-learning", ["Machine Learning", "Python", "scikit-learn", "NumPy"]),
    ("data-science", ["Python", "Pandas", "SQL", "Data Analysis", "Matplotlib"]),
    ("artificial-intelligence", ["AI", "Python", "TensorFlow", "Neural Networks"]),
    ("deep-learning", ["Deep Learning", "PyTorch", "Python", "CUDA"]),
    ("computer-vision", ["Computer Vision", "OpenCV", "Python", "CNNs"]),
    ("natural-language-processing", ["NLP", "Python", "HuggingFace", "Transformers"]),
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


async def fetch() -> list[FetchedJob]:
    jobs: list[FetchedJob] = []
    async with httpx.AsyncClient(
        timeout=20,
        headers=_HEADERS,
        follow_redirects=True,
    ) as client:
        for category, default_skills in _CATEGORIES:
            try:
                r = await client.get(
                    f"https://internshala.com/internships/{category}-internship/"
                )
                if r.status_code == 200:
                    parsed = _parse_page(r.text, category, default_skills)
                    jobs.extend(parsed)
                    logger.debug("Internshala %s: %d listings", category, len(parsed))
                else:
                    logger.warning("Internshala %s returned %d", category, r.status_code)
                await asyncio.sleep(1.5)
            except Exception as exc:
                logger.warning("Internshala %s failed: %s", category, exc)

    return _dedup(jobs)


def _parse_page(html: str, category: str, default_skills: list[str]) -> list[FetchedJob]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[FetchedJob] = []

    # Primary selector: id="internship_id_XXXXX" divs
    cards = soup.select("[id^='internship_id_']")
    if not cards:
        # Fallback: class-based selector used in some page variants
        cards = soup.select(".individual_internship")

    for card in cards:
        try:
            # Extract numeric ID from the element id attribute
            raw_id = card.get("id", "")
            iid_match = re.search(r"(\d+)$", raw_id)
            if not iid_match:
                continue
            iid = iid_match.group(1)

            title = _text(card, [
                ".job-internship-name",
                "h3.job-internship-name",
                ".profile",
            ])
            company = _text(card, [
                ".company-name",
                ".link_company_name",
                "a.link_company_name",
            ])
            location = _text(card, [
                ".locations span a",
                ".locations span",
                ".location_link",
            ]) or "India"
            stipend = _text(card, [".stipend", ".stipend_container .stipend"])
            duration = _text(card, [".other-detail-item .other-details"])

            if not title or not company:
                continue

            results.append(FetchedJob(
                title=title,
                company=company,
                source="internshala",
                external_id=f"is_{iid}",
                url=f"https://internshala.com/internship/detail/{iid}",
                location=location,
                description=f"{title} internship at {company}. Duration: {duration or 'see listing'}.",
                skills=default_skills,
                stipend=stipend or None,
                deadline=None,
                job_type="internship",
            ))
        except Exception:
            continue

    return results


def _text(tag, selectors: list[str]) -> str:
    """Try selectors in order, return first non-empty text found."""
    for sel in selectors:
        el = tag.select_one(sel)
        if el:
            t = el.get_text(separator=" ", strip=True)
            if t:
                return t
    return ""


def _dedup(jobs: list[FetchedJob]) -> list[FetchedJob]:
    seen: set[str] = set()
    out = []
    for j in jobs:
        if j.external_id not in seen:
            seen.add(j.external_id)
            out.append(j)
    return out

"""Internshala scraper — highest-volume India internship portal.

Uses httpx + BeautifulSoup. Adds a polite 1.5s delay between category pages.
Fetches 6 ML/AI categories. Respects robots.txt intent by not flooding requests.
"""
from __future__ import annotations

import asyncio
import logging

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

    # The listing page uses .individual_internship for each card.
    # Each card contains an <a href="/internship/detail/{slug}{id}"> anchor —
    # that href is the canonical URL and must be extracted directly because
    # the numeric suffix in the URL differs from the card's element ID.
    cards = soup.select(".individual_internship")
    if not cards:
        cards = soup.select("[id^='internship_id_']")

    for card in cards:
        try:
            # Extract the canonical detail URL from the anchor inside the card
            link_el = card.select_one("a[href*='/internship/detail/']")
            if not link_el:
                continue
            href = link_el.get("href", "").strip()
            if not href:
                continue
            url = f"https://internshala.com{href}" if href.startswith("/") else href
            # Use the full href path tail as a stable external_id
            external_id = f"is_{href.rstrip('/').split('/')[-1]}"

            title = _text(card, [
                ".profile",
                ".job-internship-name",
                "h3.job-internship-name",
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
            stipend_raw = _text(card, [".stipend", ".stipend_container .stipend"])
            # Treat "Unpaid" as no stipend rather than storing misleading text
            stipend = stipend_raw if stipend_raw and stipend_raw.lower() not in ("unpaid", "0") else None
            duration = _text(card, [".other-detail-item .other-details", ".duration"])

            if not title or not company:
                continue

            desc = f"{title} at {company}"
            if location:
                desc += f" — {location}"
            if duration:
                desc += f". Duration: {duration}."

            results.append(FetchedJob(
                title=title,
                company=company,
                source="internshala",
                external_id=external_id,
                url=url,
                location=location,
                description=desc,
                skills=default_skills,
                stipend=stipend,
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

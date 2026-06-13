"""Job fetcher orchestrator.

Runs all source fetchers concurrently, upserts results into the opportunities
table (keyed on source + external_id), and prunes listings that are either:
  - past their deadline date, or
  - not refreshed within STALE_DAYS days.

Seeded/manual listings (source IS NULL) are never pruned.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import AsyncSessionLocal
from ...models.db import Opportunity
from ...services import embedding_service
from . import adzuna, internshala, unstop
from .normalizer import FetchedJob

logger = logging.getLogger(__name__)

STALE_DAYS = 30


async def run() -> dict:
    """Public entry point: fetch → upsert → prune. Returns stats dict.

    Creates its own DB session so it can be called from the scheduler
    (outside a request context) or from the admin endpoint.
    """
    async with AsyncSessionLocal() as db:
        stats = {"fetched": 0, "upserted": 0, "pruned": 0, "errors": []}
        try:
            results = await asyncio.gather(
                _safe("adzuna", adzuna.fetch),
                _safe("internshala", internshala.fetch),
                _safe("unstop", unstop.fetch),
            )

            all_jobs: list[FetchedJob] = []
            for name, jobs, err in results:
                if err:
                    stats["errors"].append(f"{name}: {err}")
                    logger.warning("Fetcher %s error: %s", name, err)
                else:
                    all_jobs.extend(jobs)
                    logger.info("Fetcher %s: %d listings", name, len(jobs))

            stats["fetched"] = len(all_jobs)
            stats["upserted"] = await _upsert_all(db, all_jobs)
            stats["pruned"] = await _prune_stale(db)

            logger.info("Job refresh complete: %s", stats)
        except Exception as exc:
            logger.error("Job refresh top-level error: %s", exc)
            stats["errors"].append(str(exc))

    return stats


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _safe(name: str, fetcher) -> tuple[str, list[FetchedJob], str | None]:
    try:
        return name, await fetcher(), None
    except Exception as exc:
        return name, [], str(exc)


async def _upsert_all(db: AsyncSession, jobs: list[FetchedJob]) -> int:
    count = 0
    for job in jobs:
        if not job.title or not job.company or not job.external_id:
            continue
        try:
            result = await db.execute(
                select(Opportunity).where(
                    Opportunity.source == job.source,
                    Opportunity.external_id == job.external_id,
                )
            )
            existing = result.scalar_one_or_none()
            embedding = await embedding_service.embed(job.embed_text)
            now = datetime.utcnow()

            if existing:
                existing.title = job.title
                existing.company = job.company
                existing.location = job.location
                existing.description = job.description
                existing.required_skills = job.skills
                existing.stipend = job.stipend
                existing.deadline = job.deadline
                existing.url = job.url
                existing.embedding = embedding
                existing.is_active = True
                existing.fetched_at = now
            else:
                db.add(Opportunity(
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    description=job.description,
                    required_skills=job.skills,
                    url=job.url,
                    deadline=job.deadline,
                    type=job.job_type,
                    stipend=job.stipend,
                    embedding=embedding,
                    is_active=True,
                    fetched_at=now,
                    source=job.source,
                    external_id=job.external_id,
                ))
            count += 1
        except Exception as exc:
            logger.warning("Upsert failed [%s/%s]: %s", job.source, job.external_id, exc)

    await db.commit()
    return count


async def _prune_stale(db: AsyncSession) -> int:
    cutoff = datetime.utcnow() - timedelta(days=STALE_DAYS)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    total = 0

    # Listings not refreshed within STALE_DAYS (auto-fetched only, not manual seeds)
    r1 = await db.execute(
        delete(Opportunity).where(
            Opportunity.source.isnot(None),
            Opportunity.fetched_at < cutoff,
        )
    )
    total += r1.rowcount or 0

    # Listings whose deadline has passed (YYYY-MM-DD format only)
    r2 = await db.execute(
        text(r"""
            DELETE FROM opportunities
            WHERE source IS NOT NULL
              AND deadline IS NOT NULL
              AND deadline ~ '^\d{4}-\d{2}-\d{2}$'
              AND deadline < :today
        """),
        {"today": today_str},
    )
    total += r2.rowcount or 0

    await db.commit()
    return total

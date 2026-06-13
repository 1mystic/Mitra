"""APScheduler setup — refreshes job listings at 6 AM and 6 PM IST every day."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_refresh() -> None:
    # Import here to avoid circular imports at module load time
    from .services.job_fetcher import run
    logger.info("Scheduled job refresh starting...")
    try:
        stats = await run()
        logger.info("Scheduled refresh done: %s", stats)
    except Exception as exc:
        logger.error("Scheduled refresh failed: %s", exc)


def start() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    _scheduler.add_job(
        _run_refresh,
        # 6 AM and 6 PM IST
        CronTrigger(hour="6,18", minute=0, timezone="Asia/Kolkata"),
        id="refresh_jobs",
        replace_existing=True,
        misfire_grace_time=300,   # run within 5 min if server was down at fire time
    )
    _scheduler.start()
    logger.info("Job scheduler started — fires at 06:00 and 18:00 IST daily")


def stop() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Job scheduler stopped")


def is_running() -> bool:
    return bool(_scheduler and _scheduler.running)


def get_jobs() -> list[dict]:
    if not _scheduler:
        return []
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in _scheduler.get_jobs()
    ]

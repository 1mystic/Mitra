"""Admin endpoints — protected by Bearer token, for manual operations."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from .. import scheduler
from ..routers.auth import _decode_token
from ..services.job_fetcher import run as _refresh

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_auth(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    return _decode_token(authorization.removeprefix("Bearer ").strip())


@router.post("/refresh-jobs")
async def refresh_jobs(authorization: str | None = Header(None)):
    """Trigger a full job refresh and return stats when complete.

    Waits for the refresh to finish and returns the full stats dict
    including per-source counts.
    Requires a valid Bearer token (any authenticated user can trigger).
    """
    _require_auth(authorization)
    stats = await _refresh()
    return stats


@router.get("/scheduler-status")
async def scheduler_status(authorization: str | None = Header(None)):
    """Return registered APScheduler jobs and their next run times."""
    _require_auth(authorization)
    jobs = scheduler.get_jobs()
    return {
        "running": scheduler.is_running(),
        "jobs": jobs,
    }

"""Admin endpoints — protected by Bearer token, for manual operations."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from ..routers.auth import _decode_token
from ..services.job_fetcher import run as _refresh

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_auth(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    return _decode_token(authorization.removeprefix("Bearer ").strip())


@router.post("/refresh-jobs")
async def refresh_jobs(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    """Trigger a full job refresh immediately (runs in background).

    Returns immediately — check logs for completion stats.
    Requires a valid Bearer token (any authenticated user can trigger).
    """
    _require_auth(authorization)
    background_tasks.add_task(_refresh)
    return {"status": "refresh started", "message": "Check server logs for stats"}


@router.post("/refresh-jobs/sync")
async def refresh_jobs_sync(authorization: str | None = Header(None)):
    """Synchronous version — waits for completion and returns stats.

    Use for testing; prefer the async version in production to avoid timeouts.
    """
    _require_auth(authorization)
    stats = await _refresh()
    return stats

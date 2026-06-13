"""
Shared fixtures for Mitra backend tests.
Uses httpx ASGITransport — no real server needed, no DB calls unless explicitly tested.
"""
import asyncio
import sys

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app

# psycopg3 requires SelectorEventLoop on Windows; pytest uses ProactorEventLoop by default
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture
async def client():
    """ASGI test client — does NOT fire the lifespan (no DB init)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

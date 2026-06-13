"""Unstop fetcher — DISABLED.

Unstop does not expose a functional public API. Their /api/public/opportunity/search-result
endpoint returns empty results. Real data requires the paid Apify scraper:
  https://apify.com/trusted_offshoot/unstop-hackathon-scraper/api

Until a working integration is available, this module returns an empty list.
"""
from __future__ import annotations

from .normalizer import FetchedJob


async def fetch() -> list[FetchedJob]:
    return []

"""Thin wrapper around the Anthropic SDK for all LLM calls in Mitra."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncIterator

import anthropic

from ..config import settings

# ── Optional local intent classifier (distill_intent.py) ─────────────────────
# Loaded lazily on first classify_intent() call when USE_LOCAL_CLASSIFIER=true.
_local_classify_fn = None


def _get_local_classifier():
    global _local_classify_fn
    if _local_classify_fn is not None:
        return _local_classify_fn

    # Add ml/ to sys.path so distill_intent can be imported from the backend
    ml_dir = Path(__file__).parent.parent.parent.parent.parent / "ml"
    if ml_dir.exists() and str(ml_dir) not in sys.path:
        sys.path.insert(0, str(ml_dir))

    try:
        import distill_intent as _di
        if settings.local_classifier_path:
            import os
            os.environ["LOCAL_CLASSIFIER_PATH"] = settings.local_classifier_path
        _local_classify_fn = _di.classify_intent
        return _local_classify_fn
    except Exception as exc:
        raise RuntimeError(
            f"USE_LOCAL_CLASSIFIER=true but failed to import distill_intent: {exc}. "
            "Check LOCAL_CLASSIFIER_PATH and ensure the ml/ checkpoint exists."
        ) from exc

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def complete(prompt: str, system: str = "", max_tokens: int = 2048) -> str:
    """Single-turn completion with the primary (Sonnet) model."""
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": settings.claude_model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    response = await _client.messages.create(**kwargs)
    return response.content[0].text


async def fast_complete(prompt: str, system: str = "", max_tokens: int = 512) -> str:
    """Fast/cheap completion via Haiku — use for routing, classification, short summaries."""
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": settings.fast_model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    response = await _client.messages.create(**kwargs)
    return response.content[0].text


async def fast_complete_json(prompt: str, system: str = "", max_tokens: int = 512) -> dict | list:
    """fast_complete + JSON parse. Falls back to empty dict on parse error."""
    raw = await fast_complete(prompt, system=system, max_tokens=max_tokens)
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


async def complete_json(prompt: str, system: str = "", max_tokens: int = 2048) -> dict | list:
    """Completion that parses and returns JSON. Falls back to empty dict on parse error."""
    raw = await complete(prompt, system=system, max_tokens=max_tokens)
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


async def stream_complete(
    prompt: str,
    system: str = "",
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """Yield text chunks as they are streamed from Claude."""
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": settings.claude_model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    async with _client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text


async def classify_intent(message: str) -> str:
    """
    Classify a user message into a routing intent label.

    Uses the local fine-tuned classifier when USE_LOCAL_CLASSIFIER=true in .env,
    otherwise calls Claude. Both paths return the same set of labels:
      opportunities | resume | gaps | roadmap | track | interview | general
    """
    if settings.use_local_classifier:
        fn = _get_local_classifier()
        loop = asyncio.get_event_loop()
        # Synchronous model inference — run in thread pool to avoid blocking event loop
        label = await loop.run_in_executor(None, fn, message)
        return label

    prompt = f"""Classify this message into exactly one intent label. Return only the label, nothing else.

Intents:
- opportunities  (find internships, jobs, hackathons, research openings)
- resume         (upload or analyze resume, extract skills)
- gaps           (skill gaps, what am I missing, how do I compare)
- roadmap        (learning plan, what to study, how to prepare)
- track          (track applications, update status, application history)
- interview      (interview prep, practice questions, mock interview)
- general        (anything else)

Message: {message}

Intent:"""
    result = await fast_complete(prompt, max_tokens=10)
    label = result.strip().lower().split()[0]
    valid = {"opportunities", "resume", "gaps", "roadmap", "track", "interview", "general"}
    return label if label in valid else "general"

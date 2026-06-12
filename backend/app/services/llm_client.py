"""Thin wrapper around the Anthropic SDK for all LLM calls in Mitra."""
from __future__ import annotations

import json
from typing import AsyncIterator

import anthropic

from ..config import settings

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def complete(prompt: str, system: str = "", max_tokens: int = 2048) -> str:
    """Single-turn completion. Returns the full response as a string."""
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": settings.claude_model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    response = await _client.messages.create(**kwargs)
    return response.content[0].text


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
    """Classify a user message into a routing intent."""
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
    result = await complete(prompt, max_tokens=20)
    label = result.strip().lower().split()[0]
    valid = {"opportunities", "resume", "gaps", "roadmap", "track", "interview", "general"}
    return label if label in valid else "general"

import os
import json
from typing import Tuple, Dict, List

from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from .budget import get_or_init_settings, check_budget_and_maybe_off


# Default to a project-allowed model for Chat Completions
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-chat-latest")
# Inisialisasi klien secara aman: jika tidak ada API key, biarkan None agar tidak error saat import
_KEY = os.getenv("OPENAI_API_KEY")
_client = OpenAI(api_key=_KEY) if _KEY else None


def ask_llm(prompt: str) -> Tuple[str, Dict[str, int]]:
    """Ask Chat Completions, return (text, usage).
    If OPENAI_JSON_STRICT is truthy, request JSON-only output via response_format.
    """
    if _client is None:
        return "", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    strict = os.getenv("OPENAI_JSON_STRICT", "").strip().lower() in {"1", "true", "yes", "on"}
    kwargs = {}
    if strict:
        # Require valid JSON object response
        kwargs["response_format"] = {"type": "json_object"}

    resp = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "Kamu analis kripto. Jawab dalam JSON valid (object) tanpa teks lain."},
            {"role": "user", "content": prompt},
        ],
        **kwargs,
    )
    text = resp.choices[0].message.content or ""
    usage = {
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
        "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
        "total_tokens": getattr(resp.usage, "total_tokens", 0),
    }
    return text, usage


async def should_use_llm(db: AsyncSession) -> tuple[bool, str | None]:
    """Check admin toggle and budget, auto-disable if exceeded.
    Returns (allowed, reason_if_denied).
    """
    s = await get_or_init_settings(db)
    if not s.use_llm:
        return False, "LLM off by admin"
    # If already exceeded, auto-off
    if await check_budget_and_maybe_off(db):
        return False, "LLM auto-off: limit reached"
    return True, None


def ask_llm_messages(messages: List[Dict[str, str]]) -> Tuple[str, Dict[str, int]]:
    """Chat Completions with explicit messages. Returns (text, usage).
    Honors OPENAI_JSON_STRICT to require JSON object responses.
    """
    if _client is None:
        return "", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    strict = os.getenv("OPENAI_JSON_STRICT", "").strip().lower() in {"1", "true", "yes", "on"}
    kwargs = {}
    if strict:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        **kwargs,
    )
    text = resp.choices[0].message.content or ""
    usage = {
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
        "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
        "total_tokens": getattr(resp.usage, "total_tokens", 0),
    }
    return text, usage

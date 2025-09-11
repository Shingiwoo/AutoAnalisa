import os
import json
from typing import Tuple, Dict

from openai import OpenAI


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
# Inisialisasi klien secara aman: jika tidak ada API key, biarkan None agar tidak error saat import
_KEY = os.getenv("OPENAI_API_KEY")
_client = OpenAI(api_key=_KEY) if _KEY else None


def ask_llm(prompt: str) -> Tuple[str, Dict[str, int]]:
    """Ask Chat Completions, return (text, usage).
    No response_format usage to avoid schema issues.
    """
    # Jika tidak ada client (tidak ada API key), kembalikan fallback kosong agar tidak memblokir test/dev
    if _client is None:
        return "", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    resp = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "Kamu analis kripto. Jawab dalam JSON ringkas untuk narasi saja (field narrative)."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    text = resp.choices[0].message.content or ""
    usage = {
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
        "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
        "total_tokens": getattr(resp.usage, "total_tokens", 0),
    }
    return text, usage

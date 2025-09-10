import os
import json
from typing import Tuple, Dict

from openai import OpenAI


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_llm(prompt: str) -> Tuple[str, Dict[str, int]]:
    """Ask Chat Completions, return (text, usage).
    No response_format usage to avoid schema issues.
    """
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

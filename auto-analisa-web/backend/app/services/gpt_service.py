from __future__ import annotations
from typing import Literal, Dict, Any, Tuple
import json

from .prompt_templates import prompt_scalping, prompt_swing
from .llm import ask_llm_messages


def build_prompt(symbol: str, mode: Literal['scalping','swing'], payload: Dict[str, Any]) -> str:
    if (mode or 'scalping').lower() == 'scalping':
        return prompt_scalping(symbol, payload)
    return prompt_swing(symbol, payload)


def call_gpt(prompt: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    messages = [
        {"role": "system", "content": "Anda asisten trading Futures. Keluarkan hanya JSON valid (object) tanpa penjelasan lain."},
        {"role": "user", "content": prompt},
    ]
    text, usage = ask_llm_messages(messages)
    data: Dict[str, Any] = {}
    try:
        if text:
            data = json.loads(text)
            if not isinstance(data, dict):
                data = {}
    except Exception:
        data = {}
    return data, (usage or {})


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
        {"role": "system", "content": (
            "Anda analis trading kripto profesional. KELUARKAN HANYA JSON VALID (object) tanpa penjelasan. "
            "ANTI-BIAS: Hindari default LONG/SHORT. Jika sinyal lemah atau bertentangan, lebihkan skenario konservatif (WARNING) ketimbang NO-TRADE. "
            "Gunakan NO-TRADE hanya pada kondisi ekstrim (volatilitas/berita/likuiditas). "
            "Prioritas konfirmasi: (1) sweep & reclaim; (2) break & hold vs break & fail; (3) hindari entry tepat di magnet (00/50, high/low harian)."
        )},
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

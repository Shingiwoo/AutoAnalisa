import os
import json
import hashlib
import asyncio
from typing import Dict, Any, Optional

from openai import OpenAI


ANALISA_SCHEMA = {
    "name": "spot_plan_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "bias": {"type": "string"},
            "support": {"type": "array", "items": {"type": ["number", "array"]}},
            "resistance": {"type": "array", "items": {"type": ["number", "array"]}},
            "plan": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "pullback": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "entries": {"type": "array", "items": {"type": "number"}},
                            "invalid": {"type": "number"},
                            "tp": {"type": "array", "items": {"type": "number"}},
                        },
                        "required": ["entries", "invalid", "tp"],
                    },
                    "breakout": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "trigger_limit": {"type": "array", "items": {"type": "number"}},
                            "retest_zone": {"type": ["array", "string"]},
                            "sl_fast": {"type": "number"},
                            "tp": {"type": "array", "items": {"type": "number"}},
                        },
                        "required": ["trigger_limit", "sl_fast", "tp"],
                    },
                },
                "required": ["pullback", "breakout"],
            },
            "signals": {"type": "string"},
            "fundamental": {"type": "string"},
        },
        "required": ["bias", "support", "resistance", "plan"],
        "strict": True,
    },
}


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5")
        self.timeout_s = int(os.getenv("LLM_TIMEOUT_S", "20"))
        self.client = OpenAI(api_key=self.api_key)

    @staticmethod
    def _hash_payload(di: Dict[str, Any]) -> str:
        payload = json.dumps(di, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def summarize(self, plan_numbers: Dict[str, Any], features: Dict[str, Any]) -> Dict[str, Any]:
        """Ringkas ke format Analisa SPOT I (JSON) sesuai schema. Jangan ubah angka plan_numbers."""
        body = {"plan": plan_numbers, "features": features}
        system = (
            "Anda adalah analis crypto spot. Hasilkan Analisa SPOT I ringkas (maks 2 TP), "
            "dengan menjaga agar angka level/TP/SL TIDAK diubah dari 'plan'."
        )
        user = (
            "Buat Analisa SPOT I dalam Bahasa Indonesia. Isi field JSON sesuai schema. "
            "Singkatkan narasi, dan tambahkan 'signals' dan 'fundamental' ringkas 24–48 jam.\n"
            f"DATA: {json.dumps(body, ensure_ascii=False)}"
        )

        def _call():
            return self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_schema", "json_schema": ANALISA_SCHEMA},
            )

        resp = await asyncio.get_event_loop().run_in_executor(None, _call)
        # upaya parsing aman
        out = None
        if hasattr(resp, "output"):
            try:
                out = resp.output[0].content[0].text
            except Exception:
                pass
        if out is None and hasattr(resp, "choices"):
            try:
                out = resp.choices[0].message["content"]
            except Exception:
                pass
        if isinstance(out, str):
            return json.loads(out)
        if isinstance(out, dict):
            return out
        # fallback: dump whole
        return {"bias": "", "signals": "", "fundamental": ""}


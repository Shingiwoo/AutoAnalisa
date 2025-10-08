from typing import Optional

from app.v2_schemas.market import MarketSnapshot
from app.v2_schemas.llm_output import LlmOutput
from app.v2_payloads.build import build
from app.services_v2.llm_client import LlmClient
from app.services_v2.validators import validate_output
from app.services_v2.btc_bias import infer_btc_bias_from_exchange

ALLOWED_FOR = {
    "bullish_overbought": ["bullish"],
    "bullish_cooling": ["bullish"],
    "neutral": ["bullish", "bearish", "neutral"],
    "bearish_mild": ["bearish"],
}


def _derive_btc_bias_from_context(snapshot: MarketSnapshot) -> Optional[str]:
    try:
        rsi = snapshot.btc_context.rsi_h1 if snapshot.btc_context else None
        if rsi is None:
            return None
        if rsi >= 70:
            return "bullish_overbought"
        if rsi >= 55:
            return "bullish_cooling"
        if rsi >= 45:
            return "neutral"
        return "bearish_mild"
    except Exception:
        return None


def _reconcile_with_btc_bias(data: dict, btc_bias: Optional[str], follow_btc_bias: bool = True) -> dict:
    if not btc_bias:
        data.setdefault("btc_alignment", "neutral")
        return data
    plan = (data or {}).get("plan", {}) or {}
    bias = (plan.get("bias") or "").lower()
    allowed = ALLOWED_FOR.get(btc_bias, ["bullish", "bearish", "neutral"])
    aligned = (bias in allowed) if bias else True
    data["btc_alignment"] = "aligned" if aligned else "conflict"
    data["btc_bias_used"] = btc_bias
    # We purposely don't mutate entries due to lack of explicit side labels.
    # Frontend can warn based on btc_alignment; future work may filter entries if side is present.
    return data


async def analyze(snapshot: MarketSnapshot, follow_btc_bias: bool = True) -> LlmOutput:
    # Ensure btc_bias exists: from context if present; else try live inference
    btc_bias = snapshot.btc_bias or _derive_btc_bias_from_context(snapshot)
    if not btc_bias:
        try:
            btc_bias, ctx = await infer_btc_bias_from_exchange(symbol="BTCUSDT", timeframe="1h", limit=320)
            # No mutation of snapshot object; just use values for alignment and telemetry
        except Exception:
            btc_bias = None
    prompt = build(snapshot)
    client = LlmClient()
    raw = await client.structured_response(
        system=prompt.system, user=prompt.user, json_schema=prompt.json_schema
    )
    llm_obj = validate_output(raw)
    data = llm_obj.model_dump()
    data = _reconcile_with_btc_bias(data, btc_bias, follow_btc_bias=follow_btc_bias)
    return LlmOutput.model_validate(data)

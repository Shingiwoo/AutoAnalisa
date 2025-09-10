from ..services.market import fetch_bundle
from ..services.rules import Features, score_symbol
from ..services.planner import build_plan
from ..services.llm import LLMClient
import os


async def run_analyze(symbol: str, options: dict):
    bundle = await fetch_bundle(symbol, tuple(options.get("tf", ["4h", "1h", "15m"])) )
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    plan = build_plan(bundle, feat, score, options.get("mode", "auto"))

    # Ringkas fitur minimal untuk LLM (hemat token)
    f1 = feat.b["1h"].iloc[-1]
    f15 = feat.b["15m"].iloc[-1]
    features = {
        "rsi": {"1h": float(f1.rsi14), "15m": float(f15.rsi14)},
        "ema_stack_ok": {
            "1h": bool(f1.ema5 > f1.ema20 > f1.ema50 > f1.ema100 > f1.ema200),
            "15m": bool(
                f15.ema5 > f15.ema20 > f15.ema50 > f15.ema100 > f15.ema200
            ),
        },
        "bb_pos": {
            "1h": "above_MB"
            if f1.close > f1.mb
            else (
                "near_MB"
                if abs(f1.close - f1.mb) / max(1e-9, f1.mb) < 0.002
                else "below_MB"
            ),
            "15m": "above_MB"
            if f15.close > f15.mb
            else (
                "near_MB"
                if abs(f15.close - f15.mb) / max(1e-9, f15.mb) < 0.002
                else "below_MB"
            ),
        },
        "atr_1h": float(f1.atr14),
    }

    use_llm = bool(
        options.get("use_llm", str(os.getenv("USE_LLM", "false")).lower() == "true")
    )
    if use_llm and os.getenv("OPENAI_API_KEY"):
        try:
            llm = LLMClient()
            llm_json = await llm.summarize(plan_numbers=plan, features=features)
            # gabungkan narasi llm ke plan (tanpa mengubah angka)
            plan["bias"] = llm_json.get("bias", plan.get("bias", ""))
            plan["narrative"] = (
                plan.get("narrative", "") + "\n" + llm_json.get("signals", "")
            ).strip()
            plan["signals"] = llm_json.get("signals", "")
            plan["fundamental"] = llm_json.get("fundamental", "")
        except Exception as e:
            # fallback rules-only jika LLM gagal
            plan["narrative"] = (
                plan.get("narrative", "") + f"\n[LLM fallback] {e}"
            ).strip()

    return plan

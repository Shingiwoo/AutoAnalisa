from __future__ import annotations
from typing import Dict


def _buf(price: float, atr15: float) -> float:
    return max(float(atr15) * 0.20, abs(float(price)) * 1e-4)


def plan_pb(bundle, levels: Dict) -> Dict:
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    s1, s2 = levels["support"][:2]
    r1, r2 = levels["resistance"][:2]
    e1 = max(s1, p - a * 0.6)
    e2 = max(s2, p - a * 1.2)
    invalid = min(e1, e2) - _buf(p, a)
    tp1 = r1
    tp2 = max(r1 + (r1 - p) * 0.6, r2)
    return {
        "mode": "PB",
        "bias": f"Pullback buy di atas {s1:.6f}",
        "support": [s1, s2],
        "resistance": [r1, r2],
        "entries": [e1, e2],
        "weights": [0.4, 0.6],
        "invalid": invalid,
        "tp": [tp1, tp2],
    }


def plan_bo(bundle, levels: Dict) -> Dict:
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    r1 = levels["resistance"][0]
    e = max(r1, p + a * 0.2)
    invalid = e - a * 1.0
    return {
        "mode": "BO",
        "bias": "Breakout buy di atas range ketat",
        "support": levels["support"],
        "resistance": levels["resistance"],
        "entries": [e],
        "weights": [1.0],
        "invalid": invalid,
        "tp": [e + a * 1.2, e + a * 2.0],
    }


def plan_rr(bundle, levels: Dict) -> Dict:
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    s1, s2 = levels["support"][:2]
    e1 = s1
    e2 = s2
    invalid = min(e1, e2) - _buf(p, a)
    return {
        "mode": "RR",
        "bias": "Range reversal dari lower band/demand",
        "support": [s1, s2],
        "resistance": levels["resistance"],
        "entries": [e1, e2],
        "weights": [0.5, 0.5],
        "invalid": invalid,
        "tp": [levels["resistance"][0], levels["resistance"][1]],
    }


def plan_sr(bundle, levels: Dict) -> Dict:
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    s1 = levels["support"][0]
    e1 = s1  # beli setelah reclaim di atas s1 (konfirmasi mesti ditangani di upstream signal)
    e2 = max(levels["support"][1], p - a)
    invalid = min(e1, e2) - _buf(p, a)
    return {
        "mode": "SR",
        "bias": "Sweep & reclaim dari support kunci",
        "support": levels["support"],
        "resistance": levels["resistance"],
        "entries": [e1, e2],
        "weights": [0.4, 0.6],
        "invalid": invalid,
        "tp": [levels["resistance"][0], levels["resistance"][1]],
    }


def plan_ff(bundle, levels: Dict, fvg=None) -> Dict:
    # fvg: dict opsional {"mid": float, "low": float}
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    if fvg:
        e1 = fvg.get("mid", p - a * 0.5)
        e2 = fvg.get("low", p - a * 1.0)
    else:
        e1 = p - a * 0.5
        e2 = p - a * 1.0
    invalid = min(e1, e2) - _buf(p, a)
    return {
        "mode": "FF",
        "bias": "Fair Value Gap fill buy",
        "support": levels["support"],
        "resistance": levels["resistance"],
        "entries": [e1, e2],
        "weights": [0.5, 0.5],
        "invalid": invalid,
        "tp": [levels["resistance"][0], levels["resistance"][1]],
    }


def assemble(bundle, levels: Dict, regime: str, extras: Dict | None = None) -> Dict:
    if regime == "TREND":
        return plan_pb(bundle, levels)
    if regime == "RANGE":
        # Prefer BO; dapat diswitch ke RR bila range melebar
        return plan_bo(bundle, levels)
    # VOLATILE: SR prioritas; FF jika ada FVG
    fvg = (extras or {}).get("fvg") if extras else None
    return plan_sr(bundle, levels) if not fvg else plan_ff(bundle, levels, fvg=fvg)

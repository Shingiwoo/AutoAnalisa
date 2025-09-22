from __future__ import annotations
from typing import Dict, List, Tuple
import math


def _confirmations(mode: str) -> Dict[str, List[str]]:
    mode = (mode or "").upper()
    if mode == "BO":
        return {
            "wajib": [
                "Breakout hanya saat slot hijau (WIB) dengan volume > MA20.",
                "Gunakan stop-limit di atas high range 1H, jangan market entry di tengah lilin.",
            ],
            "opsional": [
                "M5 momentum searah (engulfing/structure break) sebelum eksekusi.",
            ],
        }
    # default PB / SR / RR / FF
    return {
        "wajib": [
            "Tunggu 15m close reclaim VWAP + EMA20.",
            "Butuh sinyal M5: pinbar / engulfing / RSI div + lonjakan volume.",
        ],
        "opsional": [
            "Periksa order flow spot (tape) selaras sebelum entry inti.",
        ],
    }


def _buf(price: float, atr15: float) -> float:
    return max(float(atr15) * 0.20, abs(float(price)) * 1e-4)


def _tp_ladder(
    price: float,
    atr: float,
    resistances: List[float],
    swing_highs: Tuple[float, float, float] | None = None,
) -> Tuple[List[float], List[str]]:
    """Bangun 3 target TP default (static ladder + ATR + swing mapping)."""

    r1 = float(resistances[0]) if resistances else price + atr
    r2 = float(resistances[1]) if len(resistances) > 1 else r1 + atr
    r3 = float(resistances[2]) if len(resistances) > 2 else r2 + atr * 1.2

    base_tp1 = min(r1, price + atr * 1.05)
    base_tp2 = max(r2, base_tp1 + atr * 0.75)
    base_tp3 = max(r3, base_tp2 + atr * 0.9)

    if swing_highs:
        sh1, sh2, sh3 = swing_highs
        base_tp1 = max(min(base_tp1, sh1), price + atr * 0.6)
        base_tp2 = max(base_tp2, sh2)
        base_tp3 = max(base_tp3, sh3)

    def _round_ext(val: float) -> float:
        if val <= 0:
            return float(val)
        magnitude = 10 ** math.floor(math.log10(abs(val)))
        step = magnitude / 20
        if step == 0:
            return float(val)
        return math.ceil(val / step) * step

    tp1 = float(base_tp1)
    tp2 = float(base_tp2)
    tp3 = float(_round_ext(base_tp3))

    logic = [
        "Ambil profit cepat / minor R",
        "Target utama / resist 1H",
        "Ekstensi / round number",
    ]
    return [tp1, tp2, tp3], logic


def plan_pb(bundle, levels: Dict) -> Dict:
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    s1, s2 = levels["support"][:2]
    r = levels["resistance"]
    vwap15 = float(getattr(last, "vwap", p))
    ema20 = float(getattr(last, "ema20", p))
    ema50 = float(getattr(last, "ema50", p))
    dyn_core = min(max(s1, min(vwap15, ema20)), p)
    e1 = min(dyn_core, p - a * 0.45)
    e2 = min(max(s2, ema50), e1 - a * 0.35)
    invalid = min(e1, e2) - _buf(p, a)
    swings = tuple(levels.get("swing_highs", [])[:3]) or None
    tp_vals, tp_logic = _tp_ladder(p, a, r, swings if swings and len(swings) >= 3 else None)
    return {
        "mode": "PB",
        "bias": f"Pullback buy di atas {s1:.6f}",
        "support": levels["support"],
        "resistance": r,
        "entries": [e1, e2],
        "weights": [0.4, 0.6],
        "invalid": invalid,
        "tp": tp_vals,
        "tp_logic": tp_logic,
        "entry_notes": [
            "Entry inti di retest EMA20/VWAP",
            "Tambah di support lanjutan / EMA50",
        ],
        "seed_tp_profile": {"kind": "ladder_static", "qty_pct": [30, 40, 30]},
        "confirmations": _confirmations("PB"),
    }


def plan_bo(bundle, levels: Dict) -> Dict:
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    r1 = levels["resistance"][0]
    r = levels["resistance"]
    trigger = max(r1, p + a * 0.25)
    retest = trigger - max(a * 0.35, abs(trigger) * 1e-4)
    invalid = retest - a * 0.9
    swings = tuple(levels.get("swing_highs", [])[:3]) or None
    tp_vals, tp_logic = _tp_ladder(trigger, a, r, swings if swings and len(swings) >= 3 else None)
    return {
        "mode": "BO",
        "bias": "Breakout buy di atas range ketat",
        "support": levels["support"],
        "resistance": r,
        "entries": [trigger, retest],
        "weights": [0.5, 0.5],
        "invalid": invalid,
        "tp": tp_vals,
        "tp_logic": tp_logic,
        "entry_notes": [
            "Stop-limit di atas high range",
            "Re-add saat retest VWAP/R1",
        ],
        "seed_tp_profile": {
            "kind": "atr_multiple",
            "multipliers": [1.0, 1.8, 2.5],
            "qty_pct": [30, 40, 30],
        },
        "confirmations": _confirmations("BO"),
    }


def plan_rr(bundle, levels: Dict) -> Dict:
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    s1, s2 = levels["support"][:2]
    e1 = s1
    e2 = s2
    invalid = min(e1, e2) - _buf(p, a)
    swings = tuple(levels.get("swing_highs", [])[:3]) or None
    tp_vals, tp_logic = _tp_ladder(p, a, levels["resistance"], swings if swings and len(swings) >= 3 else None)
    return {
        "mode": "RR",
        "bias": "Range reversal dari lower band/demand",
        "support": levels["support"],
        "resistance": levels["resistance"],
        "entries": [e1, e2],
        "weights": [0.45, 0.55],
        "invalid": invalid,
        "tp": tp_vals,
        "tp_logic": tp_logic,
        "entry_notes": [
            "Beli di VWAP-low range",
            "Tambah di demand bawah / EMA100",
        ],
        "seed_tp_profile": {"kind": "ladder_static", "qty_pct": [30, 40, 30]},
        "confirmations": _confirmations("RR"),
    }


def plan_sr(bundle, levels: Dict) -> Dict:
    last = bundle["15m"].iloc[-1]
    p = float(getattr(last, "close"))
    a = float(getattr(last, "atr14", 0.0))
    s1 = levels["support"][0]
    e1 = s1
    e2 = max(levels["support"][1], p - a)
    invalid = min(e1, e2) - _buf(p, a)
    swings = tuple(levels.get("swing_highs", [])[:3]) or None
    tp_vals, tp_logic = _tp_ladder(p, a, levels["resistance"], swings if swings and len(swings) >= 3 else None)
    return {
        "mode": "SR",
        "bias": "Sweep & reclaim dari support kunci",
        "support": levels["support"],
        "resistance": levels["resistance"],
        "entries": [e1, e2],
        "weights": [0.4, 0.6],
        "invalid": invalid,
        "tp": tp_vals,
        "tp_logic": tp_logic,
        "entry_notes": [
            "Entry setelah reclaim support",
            "Tambah di pullback ke EMA50",
        ],
        "seed_tp_profile": {"kind": "ladder_static", "qty_pct": [30, 40, 30]},
        "confirmations": _confirmations("SR"),
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
    swings = tuple(levels.get("swing_highs", [])[:3]) or None
    tp_vals, tp_logic = _tp_ladder(p, a, levels["resistance"], swings if swings and len(swings) >= 3 else None)
    return {
        "mode": "FF",
        "bias": "Fair Value Gap fill buy",
        "support": levels["support"],
        "resistance": levels["resistance"],
        "entries": [e1, e2],
        "weights": [0.45, 0.55],
        "invalid": invalid,
        "tp": tp_vals,
        "tp_logic": tp_logic,
        "entry_notes": [
            "Isi FVG tengah",
            "Isi FVG bawah / demand kuat",
        ],
        "seed_tp_profile": {"kind": "ladder_static", "qty_pct": [30, 40, 30]},
        "confirmations": _confirmations("FF"),
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

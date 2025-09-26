from __future__ import annotations
import os
from typing import Any, Dict


def _get_env_float(name: str, default: float) -> float:
    try:
        v = float(os.getenv(name, ""))
        return v if v > 0 else default
    except Exception:
        return default


def _last(values, default=None):
    try:
        return values[-1]
    except Exception:
        return default


def _pct_dist(a: float, b: float) -> float:
    base = (abs(a) + abs(b)) / 2 or 1.0
    return abs(a - b) / base


def _nearest_round(price: float) -> float:
    # round-number magnet sederhana: 0.5 untuk harga >=1, 0.01 untuk <1
    if price is None:
        return 0.0
    step = 0.5 if price >= 1 else 0.01
    return round(price / step) * step


def evaluate_pre_signal(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heuristik ringan untuk pra-keputusan LONG/SHORT/NO-TRADE.
    Aman terhadap field hilang: default ke NO-TRADE.
    """
    tol = _get_env_float("PREPROMPT_MAGNET_TOL_PCT", 0.0015)  # 0.15%

    tf = (payload or {}).get("payload", {}).get("tf") or {}
    tf5 = tf.get("5m", {})
    tf15 = tf.get("15m", {})

    last5 = tf5.get("last")
    last15 = tf15.get("last")

    rsi5 = _last(tf5.get("rsi6_last5") or [])
    rsi15 = _last(tf15.get("rsi6_last5") or [])

    ema5 = _last(tf5.get("ema50_last5") or [])
    ema15 = _last(tf15.get("ema50_last5") or [])

    score_long = 0
    score_short = 0
    reasons = []

    # Trend sederhana: harga relatif ke EMA50
    try:
        if last5 is not None and ema5 is not None:
            if last5 > ema5:
                score_long += 1; reasons.append("5m>EMA50")
            else:
                score_short += 1; reasons.append("5m<EMA50")
        if last15 is not None and ema15 is not None:
            if last15 > ema15:
                score_long += 1; reasons.append("15m>EMA50")
            else:
                score_short += 1; reasons.append("15m<EMA50")
    except Exception:
        pass

    # RSI konfirmasi
    try:
        if isinstance(rsi5, (int, float)) and isinstance(rsi15, (int, float)):
            if rsi5 > 50 and rsi15 > 50:
                score_long += 1; reasons.append("RSI6>50")
            if rsi5 < 50 and rsi15 < 50:
                score_short += 1; reasons.append("RSI6<50")
    except Exception:
        pass

    # Hindari magnet: dekat angka bulat → kurangi skor
    try:
        ref = last15 if isinstance(last15, (int, float)) else last5
        if isinstance(ref, (int, float)):
            rn = _nearest_round(ref)
            if _pct_dist(ref, rn) <= tol:
                score_long -= 1; score_short -= 1; reasons.append("near-magnet")
    except Exception:
        pass

    # Derivatif (opsional): funding & OI delta
    fut = (payload or {}).get("payload", {}).get("futures") or {}
    f_sig = (fut.get("futures_signals") or {})
    funding = f_sig.get("funding", {})
    oi = f_sig.get("oi", {})
    try:
        f_now = funding.get("now")
        if isinstance(f_now, (int, float)):
            if f_now < 0:
                score_long += 1; reasons.append("funding<0")
            if f_now > 0:
                score_short += 1; reasons.append("funding>0")
    except Exception:
        pass
    try:
        d1 = oi.get("h1")
        if isinstance(d1, (int, float)):
            if d1 < 0:
                score_long += 1; reasons.append("OI_flush_h1")
            if d1 > 0:
                score_short += 1; reasons.append("OI_up_h1")
    except Exception:
        pass

    # Keputusan akhir
    decision = "NO-TRADE"
    if score_long - score_short >= 2:
        decision = "LONG"
    elif score_short - score_long >= 2:
        decision = "SHORT"

    return {
        "decision": decision,
        "score_long": int(score_long),
        "score_short": int(score_short),
        "reasons": reasons,
    }


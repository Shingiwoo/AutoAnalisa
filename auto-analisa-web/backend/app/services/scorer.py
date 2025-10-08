from __future__ import annotations

from typing import Optional, Dict


def score_supertrend(st_trend: int) -> int:
    return 1 if int(st_trend) == 1 else -1


def score_ema50(close: float, ema50: float, atr14: Optional[float] = None, k_atr: float = 0.05) -> int:
    try:
        if atr14 is not None and abs(float(close) - float(ema50)) <= float(k_atr) * float(atr14):
            return 0
    except Exception:
        pass
    return 1 if float(close) > float(ema50) else -1


def score_rsi(val: float, bands: Dict[str, float]) -> int:
    rsi = float(val)
    long_lo = float(bands.get("long_lo", 55))
    long_hi = float(bands.get("long_hi", 70))
    short_hi = float(bands.get("short_hi", 45))
    short_lo = float(bands.get("short_lo", 30))
    mid_lo = float(bands.get("mid_lo", 45))
    mid_hi = float(bands.get("mid_hi", 55))

    if mid_lo <= rsi <= mid_hi or rsi > long_hi or rsi < short_lo:
        return 0
    if long_lo < rsi <= long_hi:
        return 1
    if short_lo <= rsi < short_hi:
        return -1
    return 0


def score_macd(macd_line: float, signal_line: float, eps: float = 0.0) -> int:
    d = float(macd_line) - float(signal_line)
    if abs(d) < float(eps):
        return 0
    return 1 if d > 0 else -1


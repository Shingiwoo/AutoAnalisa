from __future__ import annotations
import math


def round_to_step(x: float, step: float) -> float:
    k = round(float(x) / float(step)) if step else 0.0
    return float(k * float(step)) if step else float(x)


def digits_from_tick(tick: float) -> int:
    try:
        return max(0, int(round(-math.log10(float(tick)))))
    except Exception:
        return 0


def round_band_from_tick(tick: float) -> float:
    d = digits_from_tick(tick)
    return 10 ** (-(max(d - 1, 0)))


def nearest_round(price: float, tick: float) -> float:
    band = round_band_from_tick(tick)
    try:
        return round(float(price) / band) * band
    except Exception:
        return float(price)


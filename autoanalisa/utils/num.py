from __future__ import annotations

from math import floor, ceil
from typing import Optional


def round_to(x: float, step: float, mode: str = "round") -> float:
    if step is None or step == 0:
        return x
    n = x / step
    if mode == "floor":
        return floor(n) * step
    if mode == "ceil":
        return ceil(n) * step
    # round
    return round(n) * step


def position_size(risk_usdt: float, entry: float, sl: float, qty_step: Optional[float] = None) -> float:
    if entry is None or sl is None:
        return 0.0
    risk_per_unit = abs(entry - sl)
    if risk_per_unit <= 0:
        return 0.0
    qty = risk_usdt / risk_per_unit
    if qty_step:
        return round_to(qty, qty_step, mode="floor")
    return qty


def pct_targets(entry: float, perc_list: list[float], side: str) -> list[float]:
    # perc_list given in percent like [1.2, 2.2]
    prices: list[float] = []
    for p in perc_list:
        if side == "long":
            prices.append(entry * (1 + p / 100.0))
        else:
            prices.append(entry * (1 - p / 100.0))
    return prices


from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def sr_levels(df: pd.DataFrame, method: str = "pivot", n: int = 3) -> Dict[str, list]:
    highs = df["high"].rolling(window=5, center=True).max()
    lows = df["low"].rolling(window=5, center=True).min()
    resistances = sorted(highs.dropna().tail(50).unique())[-n:]
    supports = sorted(lows.dropna().tail(50).unique())[:n]
    return {
        "support": [float(x) for x in supports if np.isfinite(x)],
        "resistance": [float(x) for x in resistances if np.isfinite(x)],
    }


def confluence_tags(price: float, df, ema: dict, bb: dict, pivots: dict, tol: float = 0.001) -> list[str]:
    tags: list[str] = []
    def near(a: float, b: float) -> bool:
        return abs(a - b) / b < tol if b else False

    for k, v in ema.items():
        if v and near(price, v):
            tags.append(f"EMA{k}")
    if bb.get("middle") and near(price, float(bb["middle"])):
        tags.append("BB-mid")
    for lvl in pivots.get("support", []) + pivots.get("resistance", []):
        if near(price, float(lvl)):
            tags.append("pivot")
    return tags


def distance_tol(
    price: float,
    level: float,
    tf: str,
    atr15: float,
    atr1h: float,
    tick_size: float,
    tol_pct_min_5_15m: float = 0.0005,
    tol_pct_min_1h_4h: float = 0.0003,
    tol_atr_mult_5_15m: float = 0.15,
    tol_atr_mult_1h_4h: float = 0.10,
    ticksize_mult: float = 2.0,
) -> Tuple[float, float]:
    # distance relative to price
    distance = abs(price - level) / max(price, 1e-12)
    if tf in ("5m", "15m"):
        tol = max(
            tol_pct_min_5_15m,
            (tol_atr_mult_5_15m * (atr15 or 0.0)) / max(price, 1e-12),
            (ticksize_mult * tick_size) / max(price, 1e-12),
        )
    elif tf in ("1H", "4H"):
        tol = max(
            tol_pct_min_1h_4h,
            (tol_atr_mult_1h_4h * (atr1h or 0.0)) / max(price, 1e-12),
            (ticksize_mult * tick_size) / max(price, 1e-12),
        )
    else:
        tol = max(
            tol_pct_min_5_15m,
            (tol_atr_mult_5_15m * (atr15 or 0.0)) / max(price, 1e-12),
            (ticksize_mult * tick_size) / max(price, 1e-12),
        )
    return distance, tol


def confidence_from_tags(
    tags: List[str], distance: float, tol: float, weights: Dict[str, float], scale: float = 5.0, cap: int = 100
) -> int:
    if tol <= 0:
        return 0
    decay = max(0.0, 1.0 - distance / tol)
    score = 0.0
    for t in tags:
        w = float(weights.get(t, 0.0))
        score += w * decay
    conf = min(cap, int(round(score * scale)))
    return conf

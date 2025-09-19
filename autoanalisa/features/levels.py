from __future__ import annotations

from typing import Dict, List
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


def confluence_tags(price: float, ema: dict, bb: dict, pivots: dict, tol: float = 0.001) -> list[str]:
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


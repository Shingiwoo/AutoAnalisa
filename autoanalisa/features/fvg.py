from __future__ import annotations

from typing import List, Dict
import pandas as pd


def detect_fvg(df: pd.DataFrame, max_lookback: int = 50, tf: str = "15m") -> List[Dict]:
    res: list[dict] = []
    n = len(df)
    if n < 3:
        return res
    # Use last max_lookback windows
    start = max(2, n - max_lookback)
    for i in range(start, n):
        # bull FVG if current low > high two bars ago
        low_i = float(df["low"].iloc[i])
        high_prev2 = float(df["high"].iloc[i - 2])
        # bear FVG if current high < low two bars ago
        high_i = float(df["high"].iloc[i])
        low_prev2 = float(df["low"].iloc[i - 2])
        if low_i > high_prev2:
            res.append({"tf": tf, "dir": "bull", "top": low_i, "bottom": high_prev2})
        if high_i < low_prev2:
            res.append({"tf": tf, "dir": "bear", "top": low_prev2, "bottom": high_i})
    return res


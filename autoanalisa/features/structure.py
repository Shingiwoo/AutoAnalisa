from __future__ import annotations

from typing import Literal, List, Dict, Optional
import pandas as pd


def extract_swings(df: pd.DataFrame, left: int = 2, right: int = 2) -> List[dict]:
    highs = df["high"].values
    lows = df["low"].values
    swings: List[dict] = []
    n = len(df)
    for i in range(left, n - right):
        is_piv_high = all(highs[i] >= highs[i - j - 1] for j in range(left)) and all(
            highs[i] > highs[i + j + 1] for j in range(right)
        )
        is_piv_low = all(lows[i] <= lows[i - j - 1] for j in range(left)) and all(
            lows[i] < lows[i + j + 1] for j in range(right)
        )
        if is_piv_high:
            swings.append({"type": "ph", "idx": i, "price": highs[i]})
        if is_piv_low:
            swings.append({"type": "pl", "idx": i, "price": lows[i]})
    swings.sort(key=lambda x: x["idx"])
    return swings


def last_hh_hl_lh_ll(df: pd.DataFrame, left: int = 2, right: int = 2) -> Dict[str, Optional[float]]:
    swings = extract_swings(df, left=left, right=right)
    last_highs = [s for s in swings if s["type"] == "ph"]
    last_lows = [s for s in swings if s["type"] == "pl"]
    res = {"last_hh": None, "last_hl": None, "last_lh": None, "last_ll": None}
    if len(last_highs) >= 2:
        if last_highs[-1]["price"] > last_highs[-2]["price"]:
            res["last_hh"] = float(last_highs[-1]["price"])
        else:
            res["last_lh"] = float(last_highs[-1]["price"])
    if len(last_lows) >= 2:
        if last_lows[-1]["price"] > last_lows[-2]["price"]:
            res["last_hl"] = float(last_lows[-1]["price"])
        else:
            res["last_ll"] = float(last_lows[-1]["price"])
    return res


def infer_trend(df: pd.DataFrame, ema50: float | None = None, ema200: float | None = None) -> Literal["up", "down", "side"]:
    close = float(df["close"].iloc[-1])
    if ema50 is not None and ema200 is not None:
        if close > ema50 and ema50 > ema200:
            return "up"
        if close < ema50 and ema50 < ema200:
            return "down"
    # fallback: side if no clear
    return "side"


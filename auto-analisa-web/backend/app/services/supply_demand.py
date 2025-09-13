from __future__ import annotations
import pandas as pd
from typing import List, Dict


def _is_swing_high(df: pd.DataFrame, i: int, left: int = 1, right: int = 1) -> bool:
    if i - left < 0 or i + right >= len(df):
        return False
    h = float(df.iloc[i].high)
    for k in range(i - left, i + right + 1):
        if k == i:
            continue
        if float(df.iloc[k].high) >= h:
            return False
    return True


def _is_swing_low(df: pd.DataFrame, i: int, left: int = 1, right: int = 1) -> bool:
    if i - left < 0 or i + right >= len(df):
        return False
    l = float(df.iloc[i].low)
    for k in range(i - left, i + right + 1):
        if k == i:
            continue
        if float(df.iloc[k].low) <= l:
            return False
    return True


def detect_zones(df: pd.DataFrame, lookback: int = 500) -> List[Dict]:
    """Deteksi sederhana zona Supply/Demand berbasis swing dan range candle.
    - Supply: swing high → zona dari open..high beberapa bar ke belakang
    - Demand: swing low → zona dari low..open beberapa bar ke belakang
    Atribut: strength (kasar), fresh (belum disentuh), touched.
    """
    n = min(int(lookback or 500), len(df))
    if n < 5:
        return []
    zones: List[Dict] = []
    for i in range(len(df)):
        if _is_swing_high(df, i):
            hi = float(df.iloc[i].high)
            op = float(df.iloc[i].open)
            low = min(float(df.iloc[max(i - 3, 0): i + 1]["low"].min()), op)
            z = {"type": "supply", "i": i, "low": low, "high": hi, "fresh": True, "touched": False, "strength": 1}
            zones.append(z)
        if _is_swing_low(df, i):
            lo = float(df.iloc[i].low)
            op = float(df.iloc[i].open)
            high = max(float(df.iloc[max(i - 3, 0): i + 1]["high"].max()), op)
            z = {"type": "demand", "i": i, "low": lo, "high": high, "fresh": True, "touched": False, "strength": 1}
            zones.append(z)
    # Tandai touched (harga masuk range setelah zona terbentuk)
    for z in zones:
        for j in range(z["i"] + 1, len(df)):
            L, H = float(df.iloc[j].low), float(df.iloc[j].high)
            if H >= z["low"] and L <= z["high"]:
                z["touched"] = True
                z["fresh"] = False
                break
    return zones[-lookback:]

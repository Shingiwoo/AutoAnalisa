from __future__ import annotations
import pandas as pd
from typing import List, Dict


def detect_fvg(df: pd.DataFrame, lookback: int = 300) -> List[Dict]:
    """Deteksi Fair Value Gap sederhana berdasarkan 3-candle pattern.
    Bullish FVG: high[i-2] < low[i]
    Bearish FVG: low[i-2] > high[i]
    Menghasilkan daftar box dengan tipe, start/end index, dan level harga.
    """
    n = min(int(lookback or 300), len(df))
    if n < 3:
        return []
    hi = df["high"].values
    lo = df["low"].values
    out: List[Dict] = []
    # i sebagai indeks candle ke-3 dari pola (0-based)
    for i in range(2, len(df)):
        # bullish gap jika high[i-2] < low[i]
        if hi[i - 2] < lo[i]:
            out.append({
                "type": "bull",
                "i0": i - 2,
                "i2": i,
                "gap_low": float(hi[i - 2]),
                "gap_high": float(lo[i]),
                "mitigated": False,
            })
        # bearish gap jika low[i-2] > high[i]
        if lo[i - 2] > hi[i]:
            out.append({
                "type": "bear",
                "i0": i - 2,
                "i2": i,
                "gap_low": float(hi[i]),
                "gap_high": float(lo[i - 2]),
                "mitigated": False,
            })
    # Tandai mitigasi (sederhana): jika harga menyentuh box kemudian
    for box in out:
        lb, ub = float(box["gap_low"]), float(box["gap_high"])
        # cek bar setelah i2
        for j in range(box["i2"] + 1, len(df)):
            L, H = float(df.iloc[j].low), float(df.iloc[j].high)
            # bila range candle menyentuh area gap
            if (L <= ub and H >= lb):
                box["mitigated"] = True
                break
    return out[-lookback:]


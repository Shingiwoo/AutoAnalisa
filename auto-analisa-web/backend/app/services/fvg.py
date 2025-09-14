from __future__ import annotations
import pandas as pd
from typing import List, Dict


def detect_fvg(
    df: pd.DataFrame,
    lookback: int = 300,
    *,
    use_bodies: bool = False,
    fill_rule: str = "any_touch",  # any_touch|50pct|full
    threshold_pct: float = 0.0,
    threshold_auto: bool = False,
) -> List[Dict]:
    """Deteksi Fair Value Gap berdasarkan 3-candle pattern.
    - Bullish FVG: (wick mode) high[i-2] < low[i]. (body mode) max(open/close)[i-2] < min(open/close)[i]
    - Bearish FVG: (wick mode) low[i-2] > high[i]. (body mode) min(open/close)[i-2] > max(open/close)[i]
    - Status mitigated: jika candle berikutnya menyentuh area (any_touch) atau terisi >=50% (50pct) atau penuh (full).
    - Menambahkan ts_start (ms) untuk overlay visual; extend to right (tidak ada ts_end).
    """
    n = min(int(lookback or 300), len(df))
    if n < 3:
        return []
    hi = df["high"].values
    lo = df["low"].values
    op = df["open"].values
    cl = df["close"].values
    ts = df["ts"].values if "ts" in df.columns else [None] * len(df)
    # threshold seperti Pine: auto -> mean(range/low) terakhir lookback; else pakai threshold_pct/100
    if threshold_auto:
        rng = (df["high"] - df["low"]) / df["low"].replace(0, pd.NA)
        thr = float(rng.tail(min(lookback, len(df))).mean(skipna=True) or 0.0)
    else:
        thr = float(threshold_pct or 0.0) / 100.0
    out: List[Dict] = []
    # i sebagai indeks candle ke-3 dari pola (0-based)
    for i in range(2, len(df)):
        if use_bodies:
            prev_max_body = max(op[i - 2], cl[i - 2])
            curr_min_body = min(op[i], cl[i])
            prev_min_body = min(op[i - 2], cl[i - 2])
            curr_max_body = max(op[i], cl[i])
            bull_gap = (prev_max_body < curr_min_body) and (cl[i-1] > prev_max_body) and ((curr_min_body - prev_max_body) / max(prev_max_body, 1e-9) > thr)
            bear_gap = (prev_min_body > curr_max_body) and (cl[i-1] < prev_min_body) and ((prev_min_body - curr_max_body) / max(curr_max_body, 1e-9) > thr)
            bull_low, bull_high = prev_max_body, curr_min_body
            bear_low, bear_high = curr_max_body, prev_min_body
        else:
            bull_gap = (hi[i - 2] < lo[i]) and (cl[i-1] > hi[i-2]) and ((lo[i] - hi[i-2]) / max(hi[i-2], 1e-9) > thr)
            bear_gap = (lo[i - 2] > hi[i]) and (cl[i-1] < lo[i-2]) and ((lo[i-2] - hi[i]) / max(hi[i], 1e-9) > thr)
            bull_low, bull_high = hi[i - 2], lo[i]
            bear_low, bear_high = hi[i], lo[i - 2]

        if bull_gap:
            out.append({
                "type": "bull",
                "i0": i - 2,
                "i2": i,
                "gap_low": float(bull_low),
                "gap_high": float(bull_high),
                "ts_start": int(ts[i - 2]) if ts[i - 2] is not None else None,
                "mitigated": False,
            })
        if bear_gap:
            out.append({
                "type": "bear",
                "i0": i - 2,
                "i2": i,
                "gap_low": float(bear_low),
                "gap_high": float(bear_high),
                "ts_start": int(ts[i - 2]) if ts[i - 2] is not None else None,
                "mitigated": False,
            })
    # Tandai mitigasi (sederhana): jika harga menyentuh box kemudian
    for box in out:
        lb, ub = float(box["gap_low"]), float(box["gap_high"])
        full = ub - lb if ub > lb else 0.0
        for j in range(box["i2"] + 1, len(df)):
            L, H = float(df.iloc[j].low), float(df.iloc[j].high)
            # sentuh area?
            touch = (L <= ub and H >= lb)
            if not touch:
                continue
            if fill_rule == "any_touch":
                box["mitigated"] = True
                break
            # hitung persen terisi oleh range candle j terhadap gap
            inter = max(0.0, min(ub, H) - max(lb, L))
            pct = (inter / full) if full > 0 else 0.0
            if (fill_rule == "50pct" and pct >= 0.5) or (fill_rule == "full" and pct >= 0.999):
                box["mitigated"] = True
                break
    return out[-lookback:]

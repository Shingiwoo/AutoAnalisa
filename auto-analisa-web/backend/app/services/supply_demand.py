from __future__ import annotations
import pandas as pd
from typing import List, Dict
import numpy as np


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


def detect_zones(
    df: pd.DataFrame,
    lookback: int = 500,
    *,
    max_base: int = 3,
    body_ratio: float = 0.33,
    min_departure: float = 1.5,  # departure candle range vs avg base range
    mode: str = "swing",
    vol_div: int = 20,
    vol_threshold_pct: float = 10.0,
) -> List[Dict]:
    """Deteksi zona Supply/Demand berbasis pola DBR/RBD sederhana.
    - Identifikasi swing high/low.
    - Basis: 1..max_base candle dengan body kecil (|close-open|/range <= body_ratio).
    - Departure: 1-2 candle sesudah basis dengan range >= min_departure * avg_range_basis.
    - Zona:
      * Supply: high = max(high basis), low = min(open/close basis).
      * Demand: low = min(low basis), high = max(open/close basis).
    - Atribut: strength (jumlah departure kuat), fresh/touched, ts_start untuk overlay.
    """
    n = min(int(lookback or 500), len(df))
    if n < 5:
        return []
    zones: List[Dict] = []
    op = df["open"].values
    cl = df["close"].values
    hi = df["high"].values
    lo = df["low"].values
    ts = df["ts"].values if "ts" in df.columns else [None] * len(df)

    def _body_ratio(i: int) -> float:
        rng = max(1e-9, hi[i] - lo[i])
        body = abs(cl[i] - op[i])
        return float(body / rng)

    if mode == "volume":
        # Approximate LuxAlgo volume-based demand/supply across lookback window
        # Compute visible range bounds
        lo_win = float(np.min(lo[-min(lookback, len(df)) :]))
        hi_win = float(np.max(hi[-min(lookback, len(df)) :]))
        if not np.isfinite(hi_win - lo_win) or (hi_win - lo_win) <= 0:
            pass
        else:
            step = (hi_win - lo_win) / max(1, int(vol_div))
            # bins edges from top (supply) and bottom (demand)
            # Simple bar-level approximation of intrabar distribution:
            total_vol = float(np.nansum(df["volume"].tail(min(lookback, len(df))).values)) or 1.0
            # supply: scan downward from hi_win until threshold bin found
            sup_prev = hi_win
            sup_low = None
            sup_sum = 0.0
            for i in range(int(vol_div)):
                sup_lvl = hi_win - (i + 1) * step
                # accumulate volume if bar high is within (sup_lvl, sup_prev)
                mask = (hi[-min(lookback, len(df)) :] < sup_prev) & (hi[-min(lookback, len(df)) :] > sup_lvl)
                sup_sum += float(np.nansum(df["volume"].tail(min(lookback, len(df))).values[mask]))
                if (sup_sum / total_vol) * 100.0 >= float(vol_threshold_pct):
                    sup_low = sup_lvl
                    break
                sup_prev = sup_lvl
            if sup_low is not None:
                zones.append({
                    "type": "supply",
                    "i": len(df) - 1,
                    "low": float(sup_low),
                    "high": float(hi_win),
                    "fresh": True,
                    "touched": False,
                    "strength": 1,
                    "ts_start": int(ts[-min(lookback, len(df))]) if ts and ts[-min(lookback, len(df))] is not None else None,
                })

            # demand: scan upward from lo_win until threshold bin found
            dem_prev = lo_win
            dem_high = None
            dem_sum = 0.0
            for i in range(int(vol_div)):
                dem_lvl = lo_win + (i + 1) * step
                mask = (lo[-min(lookback, len(df)) :] > dem_prev) & (lo[-min(lookback, len(df)) :] < dem_lvl)
                dem_sum += float(np.nansum(df["volume"].tail(min(lookback, len(df))).values[mask]))
                if (dem_sum / total_vol) * 100.0 >= float(vol_threshold_pct):
                    dem_high = dem_lvl
                    break
                dem_prev = dem_lvl
            if dem_high is not None:
                zones.append({
                    "type": "demand",
                    "i": len(df) - 1,
                    "low": float(lo_win),
                    "high": float(dem_high),
                    "fresh": True,
                    "touched": False,
                    "strength": 1,
                    "ts_start": int(ts[-min(lookback, len(df))]) if ts and ts[-min(lookback, len(df))] is not None else None,
                })
        # End volume mode (skip swing detection path below)
        # still run touched logic below

    for i in range(len(df)):
        # Kumpulkan basis di sekitar swing
        if _is_swing_high(df, i):
            base_idx = [i]
            k = i - 1
            while k >= 0 and len(base_idx) < max_base and _body_ratio(k) <= body_ratio:
                base_idx.append(k)
                k -= 1
            base_idx.sort()
            base_range = [hi[j] - lo[j] for j in base_idx]
            avg_base = sum(base_range) / max(1, len(base_range))
            # Departure kuat setelah swing?
            strength = 0
            for j in range(i + 1, min(len(df), i + 3)):
                if (hi[j] - lo[j]) >= min_departure * avg_base and cl[j] < op[j]:  # candle turun kuat
                    strength += 1
            if strength == 0:
                # keep scanning other swings; do not add zone in strict mode for this swing
                pass
            else:
                high_z = float(max(hi[j] for j in base_idx))
                low_z = float(min(op[j] if cl[j] < op[j] else cl[j] for j in base_idx))
                zones.append({
                    "type": "supply", "i": i, "low": low_z, "high": high_z,
                    "fresh": True, "touched": False, "strength": strength,
                    "ts_start": int(ts[i]) if ts[i] is not None else None,
                })
        if _is_swing_low(df, i):
            base_idx = [i]
            k = i - 1
            while k >= 0 and len(base_idx) < max_base and _body_ratio(k) <= body_ratio:
                base_idx.append(k)
                k -= 1
            base_idx.sort()
            base_range = [hi[j] - lo[j] for j in base_idx]
            avg_base = sum(base_range) / max(1, len(base_range))
            strength = 0
            for j in range(i + 1, min(len(df), i + 3)):
                if (hi[j] - lo[j]) >= min_departure * avg_base and cl[j] > op[j]:  # candle naik kuat
                    strength += 1
            if strength == 0:
                pass
            else:
                low_z = float(min(lo[j] for j in base_idx))
                high_z = float(max(op[j] if cl[j] > op[j] else cl[j] for j in base_idx))
                zones.append({
                    "type": "demand", "i": i, "low": low_z, "high": high_z,
                    "fresh": True, "touched": False, "strength": strength,
                    "ts_start": int(ts[i]) if ts[i] is not None else None,
                })
    # Tandai touched (harga masuk range setelah zona terbentuk)
    for z in zones:
        for j in range(z["i"] + 1, len(df)):
            L, H = float(df.iloc[j].low), float(df.iloc[j].high)
            if H >= z["low"] and L <= z["high"]:
                z["touched"] = True
                z["fresh"] = False
                break

    # Fallback (lebih longgar) bila tidak ada zona yang lolos kriteria strict
    if not zones:
        for i in range(len(df)):
            if _is_swing_high(df, i):
                z = {
                    "type": "supply",
                    "i": i,
                    "low": float(min(df.iloc[max(i-2,0):i+1]["open"].min(), df.iloc[max(i-2,0):i+1]["close"].min())),
                    "high": float(df.iloc[max(i-2,0):i+1]["high"].max()),
                    "fresh": True,
                    "touched": False,
                    "strength": 1,
                    "ts_start": int(ts[i]) if ts[i] is not None else None,
                }
                zones.append(z)
            if _is_swing_low(df, i):
                z = {
                    "type": "demand",
                    "i": i,
                    "low": float(df.iloc[max(i-2,0):i+1]["low"].min()),
                    "high": float(max(df.iloc[max(i-2,0):i+1]["open"].max(), df.iloc[max(i-2,0):i+1]["close"].max())),
                    "fresh": True,
                    "touched": False,
                    "strength": 1,
                    "ts_start": int(ts[i]) if ts[i] is not None else None,
                }
                zones.append(z)

    return zones[-lookback:]

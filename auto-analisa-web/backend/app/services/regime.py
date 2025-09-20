from __future__ import annotations
from typing import Dict
import numpy as np

# bundle: dict {"15m": df15, "1h": df1, "4h": df4, "1d": dfD}
# DataFrame diharapkan sudah memiliki kolom: close, ema20, ema50, ema100, ub, dn, mb, atr14


def detect_regime(bundle) -> Dict:
    df15, df1 = bundle.get("15m"), bundle.get("1h")
    if df15 is None or df1 is None:
        return {"regime": "VOLATILE", "confidence": 0.3}
    # Safety
    for df in (df15, df1):
        try:
            if len(df) < 60:
                return {"regime": "VOLATILE", "confidence": 0.3}
        except Exception:
            return {"regime": "VOLATILE", "confidence": 0.3}

    # Trend via EMA stack & slope
    try:
        slope = (df1.ema20.iloc[-1] - df1.ema20.iloc[-5]) / (abs(df1.ema20.iloc[-5]) + 1e-9)
        stack_up = (df1.ema20.iloc[-1] > df1.ema50.iloc[-1] > getattr(df1, "ema100", df1.ema50).iloc[-1])
    except Exception:
        slope = 0.0
        stack_up = False

    # Range via BB width persentil
    try:
        bw_series = (df15.ub - df15.dn) / (abs(df15.mb) + 1e-9)
        bw_now = float(bw_series.iloc[-1])
        bw_p35 = float(np.nanpercentile(bw_series.dropna().values, 35)) if bw_series.notna().any() else 0.02
    except Exception:
        bw_now = 0.0
        bw_p35 = 0.02

    # Volatile via ATR%
    try:
        atrp_series = (df15.atr14 / (abs(df15.close) + 1e-9))
        atrp_now = float(atrp_series.iloc[-1])
        atrp_p65 = float(np.nanpercentile(atrp_series.dropna().values, 65)) if atrp_series.notna().any() else 0.01
    except Exception:
        atrp_now = 0.0
        atrp_p65 = 0.01

    trend = bool(stack_up) and slope > 0
    range_ = bw_now < bw_p35
    volatile = atrp_now > atrp_p65

    if trend and not range_:
        return {"regime": "TREND", "confidence": float(min(1.0, abs(slope) * 10))}
    if range_ and not trend:
        return {"regime": "RANGE", "confidence": float(min(1.0, 1 - bw_now))}
    return {"regime": "VOLATILE", "confidence": float(min(1.0, atrp_now * 3))}


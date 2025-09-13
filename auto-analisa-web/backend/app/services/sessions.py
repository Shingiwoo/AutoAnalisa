from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict

from .market import fetch_klines


def _bootstrap_mean_ci(x: np.ndarray, iters: int = 2000, alpha: float = 0.05):
    if x.size == 0:
        return 0.0, (0.0, 0.0), 1.0
    rng = np.random.default_rng(42)
    n = x.size
    means = np.empty(iters, dtype=float)
    for i in range(iters):
        idx = rng.integers(0, n, size=n)
        means[i] = float(np.mean(x[idx]))
    lo = float(np.quantile(means, alpha / 2))
    hi = float(np.quantile(means, 1 - alpha / 2))
    m = float(np.mean(x))
    # two-sided p-value as tail probability around 0
    gt = float(np.mean(means >= 0))
    lt = float(np.mean(means <= 0))
    p = 2 * min(gt, lt)
    return m, (lo, hi), p


async def btc_wib_buckets(days: int = 120, timeframe: str = "1h") -> List[Dict]:
    # fetch enough bars; 24 per day for 1h
    min_days = max(90, int(days or 90))
    limit = int(min_days * 24 * (1 if timeframe in ("1h", "60m", "1H") else 2))
    df = await fetch_klines("BTCUSDT", timeframe if timeframe != "60m" else "1h", limit=limit)
    if df is None or len(df) == 0:
        return []
    # Compute returns per candle (close/open - 1)
    df = df.copy()
    # ccxt returns ms timestamps
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df["open"] = pd.to_numeric(df["open"])  # ensure float
    df["close"] = pd.to_numeric(df["close"])  # ensure float
    df["ret"] = (df["close"] / df["open"]) - 1.0
    # bucket by WIB hour
    jkt = ZoneInfo("Asia/Jakarta")
    df["hour_wib"] = df["ts"].dt.tz_convert(jkt).dt.hour
    out: List[Dict] = []
    N_MIN = 60  # minimum samples per bucket
    for h in range(24):
        x = df.loc[df["hour_wib"] == h, "ret"].to_numpy(dtype=float)
        n = int(x.size)
        if n < N_MIN:
            continue
        mean, (lo, hi), p = _bootstrap_mean_ci(x, iters=2000, alpha=0.05)
        # hit-rate: proportion of positive returns
        hit = float(np.mean(x > 0.0)) if n > 0 else 0.0
        # effect size: Cohen's d
        sd = float(np.std(x, ddof=1)) if n > 1 else 0.0
        d = (mean / sd) if sd > 0 else 0.0
        sig = (p <= 0.05) and (n >= N_MIN)
        if sig:
            out.append({
                "hour": h,
                "n": n,
                "mean": round(mean, 6),
                "hit_rate": round(hit, 4),
                "ci_low": round(lo, 6),
                "ci_high": round(hi, 6),
                "p_value": round(p, 6),
                "effect": round(d, 4),
                "tz": "Asia/Jakarta",
            })
    # sort by hour
    out.sort(key=lambda r: r["hour"])
    return out


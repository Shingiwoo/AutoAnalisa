from __future__ import annotations

import os
import time
from typing import Optional, Dict, Tuple

try:
    import ccxt
except Exception:  # pragma: no cover
    ccxt = None  # type: ignore


class OIService:
    """Open interest change provider.

    Uses Binance USDM `fetchOpenInterestHistory` if available. Returns % change over
    lookback window (default 24 hours). Falls back to 0.0 when offline.
    """

    def __init__(self, client: object | None = None):
        self.client = client or (ccxt.binanceusdm() if ccxt else None)
        self.cache: Dict[tuple, Tuple[float, float]] = {}

    def get_change(self, symbol: str, lookback_h: int = 24) -> float:
        key = (symbol.upper(), int(lookback_h))
        now = time.time()
        if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
            return 0.0
        if key in self.cache:
            ts, val = self.cache[key]
            if now - ts <= 180:  # 3 minutes
                return val
        try:
            ex = self.client
            if ex and hasattr(ex, 'fetchOpenInterestHistory'):
                # Approximate: use 1h timeframe for 24h window
                arr = ex.fetchOpenInterestHistory(symbol, timeframe='1h', limit=max(lookback_h, 2))
                if isinstance(arr, list) and len(arr) >= 2:
                    first = float(arr[0].get('openInterest') or arr[0].get('open_interest') or 0.0)
                    last = float(arr[-1].get('openInterest') or arr[-1].get('open_interest') or 0.0)
                    if first > 0:
                        chg = (last - first) / first
                        self.cache[key] = (now, float(chg))
                        return float(chg)
        except Exception:
            pass
        self.cache[key] = (now, 0.0)
        return 0.0


from __future__ import annotations

import os
import time
from datetime import timedelta
from typing import Optional, Dict, Tuple

try:
    import ccxt
except Exception:  # pragma: no cover
    ccxt = None  # type: ignore


class FundingService:
    """Simple funding-rate fetcher with small in-memory cache.

    Returns a decimal rate per 8h (e.g., +0.0100% -> 0.0001).
    Falls back to 0.0 when offline or provider fails.
    """

    def __init__(self, client: object | None = None, ttl_seconds: int = 180):
        self.client = client or (ccxt.binanceusdm() if ccxt else None)
        self.cache: Dict[str, Tuple[float, float]] = {}
        self.ttl = float(ttl_seconds)

    def get(self, symbol: str) -> Optional[float]:
        key = symbol.upper()
        now = time.time()
        # Offline shortcut
        if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
            return 0.0
        # Cached
        if key in self.cache:
            ts, val = self.cache[key]
            if now - ts <= self.ttl:
                return val
        # Provider
        try:
            ex = self.client
            if ex and hasattr(ex, "fetchFundingRate"):
                fr = ex.fetchFundingRate(symbol)
                val = float(fr.get("fundingRate") or 0.0)
                self.cache[key] = (now, val)
                return val
        except Exception:
            pass
        # fallback 0
        self.cache[key] = (now, 0.0)
        return 0.0


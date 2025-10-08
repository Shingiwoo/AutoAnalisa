from __future__ import annotations

import os
from typing import List
import numpy as np


class BTCDService:
    """Stubby dominance service.

    In production, replace with a real BTC dominance feed. For now, we return a
    synthetic trend using a simple up-trend (+1) when offline. This still allows
    the context engine to operate deterministically.
    """

    def get_series(self, tf: str = '1D', limit: int = 400) -> List[float]:
        # Offline synthetic series: mildly trending up 40..45
        if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
            base = 42.0
            return list(base + np.linspace(-1.0, 1.0, int(limit)))
        # Without a real feed, return a flat series
        return [42.0 for _ in range(int(limit))]

    def get_trend(self, tf: str = '1D') -> int:
        s = self.get_series(tf=tf, limit=120)
        if not s or len(s) < 3:
            return 1
        x = np.arange(len(s))
        y = np.array(s, dtype=float)
        # slope sign via simple linear fit
        try:
            a, b = np.polyfit(x, y, 1)
            return 1 if float(a) >= 0 else -1
        except Exception:
            return 1


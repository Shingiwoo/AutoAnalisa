import time
from typing import Dict, List

import ccxt

CACHE_TTL = 3600
_state: Dict[str, object] = {"ts": 0.0, "spot": [], "futures": []}


def refresh_symbols() -> Dict[str, List[str]]:
    global _state
    ex = ccxt.binance({"enableRateLimit": True})
    markets = ex.load_markets()
    spot = sorted([
        m for m in markets
        if markets[m].get("spot") and markets[m].get("quote") == "USDT"
    ])
    futs = sorted([
        m for m in markets
        if markets[m].get("future") or markets[m].get("contract")
    ])
    _state = {"ts": time.time(), "spot": spot, "futures": futs}
    return {"spot": spot, "futures": futs}


def get_symbols(kind: str = "spot") -> List[str]:
    if kind not in ("spot", "futures"):
        raise ValueError("kind must be 'spot' or 'futures'")
    now = time.time()
    if not _state[kind] or now - float(_state.get("ts", 0.0)) > CACHE_TTL:
        refresh_symbols()
    return list(_state.get(kind) or [])

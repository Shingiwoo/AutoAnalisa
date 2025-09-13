from __future__ import annotations
from typing import Dict, Any
import math

import ccxt


_ex = ccxt.binance()
_markets_loaded = False


def _load_markets_safe():
    global _markets_loaded
    if _markets_loaded:
        return
    try:
        _ex.load_markets(reload=False)
        _markets_loaded = True
    except Exception:
        # offline or network blocked; keep fallback mode
        _markets_loaded = False


def _norm_symbol(sym: str) -> str:
    s = sym.upper().replace(":USDT", "/USDT")
    if "/" not in s and s.endswith("USDT"):
        s = f"{s[:-4]}/USDT"
    return s


def _tick_size_for(symbol: str) -> float | None:
    _load_markets_safe()
    if not _markets_loaded:
        return None
    try:
        m = _ex.market(_norm_symbol(symbol))
        # prefer precision.decimals -> min price increment
        if m and m.get("precision") and "price" in m["precision"] and isinstance(m["precision"]["price"], int):
            prec = int(m["precision"]["price"]) or 0
            return float(10 ** (-prec)) if prec > 0 else 1.0
        # else try limits.price.min
        lim = (m or {}).get("limits", {}).get("price", {})
        if lim and lim.get("min"):
            return float(lim["min"]) or None
    except Exception:
        return None
    return None


def _snap(v: float, step: float) -> float:
    if step is None or step <= 0:
        return round(float(v), 6)
    return float(math.floor(v / step + 1e-9) * step)


def round_plan_prices(symbol: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """Round all price fields in plan to exchange tick size if available.
    Fallback to 6 decimals when offline.
    """
    p = dict(plan or {})
    tick = _tick_size_for(symbol)
    if tick is None:
        # fallback already handled in validator; no-op here
        return p
    for key in ("support", "resistance", "entries", "tp"):
        arr = p.get(key)
        if isinstance(arr, list):
            p[key] = [_snap(float(x), tick) for x in arr if x is not None]
    if p.get("invalid") is not None:
        p["invalid"] = _snap(float(p["invalid"]), tick)
    return p


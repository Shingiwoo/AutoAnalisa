from __future__ import annotations
from typing import Dict, Any, List
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


def _decimals_from_tick(step: float | None) -> int:
    if step is None or step <= 0:
        return 6
    s = f"{step:.12f}".rstrip('0').rstrip('.')
    if '.' in s:
        return min(8, max(0, len(s.split('.')[1])))
    return 0


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
    p["price_decimals"] = _decimals_from_tick(tick)
    for key in ("support", "resistance", "entries", "tp"):
        arr = p.get(key)
        if isinstance(arr, list):
            p[key] = [_snap(float(x), tick) for x in arr if x is not None]
    if p.get("invalid") is not None:
        p["invalid"] = _snap(float(p["invalid"]), tick)
    return p


def round_spot2_prices(symbol: str, spot2: Dict[str, Any]) -> Dict[str, Any]:
    """Round SPOT II price fields (entries ranges, tp ranges, invalid) to exchange tick size.
    Fallback to no-op if tick size unavailable (offline).
    """
    s2 = dict(spot2 or {})
    tick = _tick_size_for(symbol)
    if tick is None:
        return s2
    s2.setdefault("metrics", {})
    s2["metrics"]["price_decimals"] = _decimals_from_tick(tick)
    # rencana_jual_beli entries + invalid
    rjb = dict(s2.get("rencana_jual_beli") or {})
    ents = []
    for e in (rjb.get("entries") or []):
        try:
            rng: List[float] = list(e.get("range") or [])
            lo = _snap(float(rng[0]), tick) if len(rng) > 0 else None
            hi = _snap(float(rng[1]), tick) if len(rng) > 1 else lo
            new_e = dict(e)
            new_e["range"] = [lo, hi] if lo is not None else rng
            ents.append(new_e)
        except Exception:
            ents.append(e)
    if ents:
        rjb["entries"] = ents
    try:
        inv = rjb.get("invalid")
        if inv is not None:
            rjb["invalid"] = _snap(float(inv), tick)
    except Exception:
        pass
    s2["rencana_jual_beli"] = rjb
    # TP nodes
    tps = []
    for t in (s2.get("tp") or []):
        try:
            rng = list(t.get("range") or [])
            lo = _snap(float(rng[0]), tick) if len(rng) > 0 else None
            hi = _snap(float(rng[1]), tick) if len(rng) > 1 else lo
            new_t = dict(t)
            new_t["range"] = [lo, hi] if lo is not None else rng
            tps.append(new_t)
        except Exception:
            tps.append(t)
    if tps:
        s2["tp"] = tps
    return s2


def round_futures_prices(symbol: str, fut: Dict[str, Any]) -> Dict[str, Any]:
    """Round FUTURES price fields (entries ranges, tp ranges, invalids tiers) to tick size.
    Fallback no-op if tick size unavailable.
    """
    s = dict(fut or {})
    tick = _tick_size_for(symbol)
    if tick is None:
        return s
    s["price_decimals"] = _decimals_from_tick(tick)
    # entries
    ents = []
    for e in (s.get("entries") or []):
        try:
            rng = list(e.get("range") or [])
            lo = _snap(float(rng[0]), tick) if len(rng) > 0 else None
            hi = _snap(float(rng[1]), tick) if len(rng) > 1 else lo
            ne = dict(e)
            ne["range"] = [lo, hi] if lo is not None else rng
            ents.append(ne)
        except Exception:
            ents.append(e)
    if ents:
        s["entries"] = ents
    # tp
    tps = []
    for t in (s.get("tp") or []):
        try:
            rng = list(t.get("range") or [])
            lo = _snap(float(rng[0]), tick) if len(rng) > 0 else None
            hi = _snap(float(rng[1]), tick) if len(rng) > 1 else lo
            nt = dict(t)
            nt["range"] = [lo, hi] if lo is not None else rng
            tps.append(nt)
        except Exception:
            tps.append(t)
    if tps:
        s["tp"] = tps
    # invalids
    try:
        inv = dict(s.get("invalids") or {})
        for k in ["tactical_5m", "soft_15m", "hard_1h", "struct_4h"]:
            if inv.get(k) is not None:
                inv[k] = _snap(float(inv.get(k)), tick)
        s["invalids"] = inv
    except Exception:
        pass
    return s

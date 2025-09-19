
from __future__ import annotations
from typing import Dict, Any, Tuple
import math
import ccxt

_ex = ccxt.binanceusdm()
_loaded = False

def _load():
    global _loaded
    if not _loaded:
        try:
            _ex.load_markets()
        except Exception:
            pass
        _loaded = True

def lot_step(symbol: str) -> Tuple[float, float]:
    _load()
    m = _ex.markets.get(symbol) or _ex.markets.get(symbol.replace("USDT", "/USDT"))
    if not m:
        return 0.01, 0.01
    return float(m.get("precision", {}).get("amount", 2)), float(m.get("precision", {}).get("price", 4))

def round_qty(symbol: str, qty: float) -> float:
    _load()
    try:
        return float(_ex.amount_to_precision(symbol, qty))
    except Exception:
        step, _ = lot_step(symbol)
        k = 10 ** step
        return math.floor(qty * k) / k

def round_price(symbol: str, price: float) -> float:
    _load()
    try:
        return float(_ex.price_to_precision(symbol, price))
    except Exception:
        _, prec = lot_step(symbol)
        k = 10 ** prec
        return math.floor(price * k) / k

def compute_position_size(symbol: str, balance_usdt: float, risk_per_trade: float,
                          leverage: int, entry_price: float, invalid_price: float) -> Dict[str, Any]:
    """Return margin, qty, notional for Binance Futures.
    margin = risk * balance
    position size (contracts) = (margin * leverage) / entry_price
    """
    risk_usd = max(0.0, balance_usdt * float(risk_per_trade))
    notional = risk_usd * float(leverage)
    raw_qty = notional / max(entry_price, 1e-9)
    qty = round_qty(symbol, raw_qty)
    return {
        "risk_usd": risk_usd,
        "notional": round(notional, 4),
        "qty": qty,
    }

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
import requests

from ..utils.time import to_tz

BASE = "https://api.binance.com"  # Spot REST


def _req(url: str, params: Optional[dict] = None) -> dict:
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_exchange_info(symbol: str) -> dict:
    data = _req(f"{BASE}/api/v3/exchangeInfo", params={"symbol": symbol})
    if "symbols" not in data or not data["symbols"]:
        raise ValueError(f"symbol not found: {symbol}")
    s = data["symbols"][0]
    price_step = None
    qty_step = None
    min_notional = None
    for f in s.get("filters", []):
        if f.get("filterType") == "PRICE_FILTER":
            price_step = float(f.get("tickSize", 0))
        elif f.get("filterType") == "LOT_SIZE":
            qty_step = float(f.get("stepSize", 0))
        elif f.get("filterType") == "NOTIONAL":
            try:
                min_notional = float(f.get("minNotional"))
            except Exception:
                min_notional = None
    precision = {
        "price": price_step if price_step else 0.0001,
        "qty": qty_step if qty_step else 0.1,
        "min_notional": min_notional if min_notional else 5.0,
    }
    # Fees per-symbol not provided by public REST; fallback typical spot
    fees = {"maker": 0.0010, "taker": 0.0010}
    return {"symbol": symbol, "precision": precision, "fees": fees}


def get_klines(symbol: str, interval: str, limit: int = 300, tz_str: str = "Asia/Jakarta") -> pd.DataFrame:
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    raw = _req(f"{BASE}/api/v3/klines", params=params)
    cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume",
        "ignore",
    ]
    df = pd.DataFrame(raw, columns=cols)
    # Convert types
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    # Last row is closed as per Binance once delivered; still we ensure tz
    df["open_time"] = df["open_time"].dt.tz_convert(tz_str)
    df["close_time"] = df["close_time"].dt.tz_convert(tz_str)
    return df[["open_time", "open", "high", "low", "close", "volume", "close_time"]]


def get_depth(symbol: str, limit: int = 5) -> dict:
    data = _req(f"{BASE}/api/v3/depth", params={"symbol": symbol, "limit": limit})
    bids = [(float(p), float(q)) for p, q in data.get("bids", [])[:limit]]
    asks = [(float(p), float(q)) for p, q in data.get("asks", [])[:limit]]
    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None
    spread = (best_ask - best_bid) if (best_ask and best_bid) else None
    bid_qty = sum(q for _, q in bids)
    ask_qty = sum(q for _, q in asks)
    ob_imbalance_5 = bid_qty / (bid_qty + ask_qty) if (bid_qty + ask_qty) > 0 else None
    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "ob_imbalance_5": ob_imbalance_5,
    }


from __future__ import annotations

from typing import Optional

import pandas as pd
import requests

from ..utils.time import to_tz

BASE = "https://fapi.binance.com"  # USDT-M Futures REST


def _req(url: str, params: Optional[dict] = None) -> dict:
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_exchange_info(symbol: str) -> dict:
    data = _req(f"{BASE}/fapi/v1/exchangeInfo")
    symbols = data.get("symbols", [])
    s = next((x for x in symbols if x.get("symbol") == symbol), None)
    if not s:
        raise ValueError(f"symbol not found: {symbol}")
    price_step = None
    qty_step = None
    for f in s.get("filters", []):
        if f.get("filterType") == "PRICE_FILTER":
            price_step = float(f.get("tickSize", 0))
        elif f.get("filterType") == "LOT_SIZE":
            qty_step = float(f.get("stepSize", 0))
        elif f.get("filterType") == "MIN_NOTIONAL":
            # Futures often has notional filter differently
            pass
    precision = {
        "price": price_step if price_step else 0.0001,
        "qty": qty_step if qty_step else 0.1,
        "min_notional": 5.0,
    }
    # Default common fees (can vary by VIP): taker 0.0004, maker 0.0002
    fees = {"maker": 0.0002, "taker": 0.0004}
    meta = {"contractType": s.get("contractType"), "marginAsset": s.get("marginAsset")}
    return {"symbol": symbol, "precision": precision, "fees": fees, "meta": meta}


def get_klines(symbol: str, interval: str, limit: int = 300, tz_str: str = "Asia/Jakarta") -> pd.DataFrame:
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    raw = _req(f"{BASE}/fapi/v1/klines", params=params)
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
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_convert(tz_str)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True).dt.tz_convert(tz_str)
    return df[["open_time", "open", "high", "low", "close", "volume", "close_time"]]


def get_mark_index(symbol: str) -> dict:
    try:
        d = _req(f"{BASE}/fapi/v1/premiumIndex", params={"symbol": symbol})
        return {"mark_price": float(d.get("markPrice")), "index_price": float(d.get("indexPrice"))}
    except Exception:
        return {"mark_price": None, "index_price": None}


def get_funding(symbol: str) -> dict:
    try:
        arr = _req(f"{BASE}/fapi/v1/fundingRate", params={"symbol": symbol, "limit": 1})
        if not arr:
            return {"funding_rate": None, "next_funding_ts": None}
        last = arr[-1]
        fr = float(last.get("fundingRate"))
        # next funding ts not directly returned; we can leave None
        return {"funding_rate": fr, "next_funding_ts": None}
    except Exception:
        return {"funding_rate": None, "next_funding_ts": None}


def get_oi(symbol: str) -> Optional[float]:
    try:
        d = _req(f"{BASE}/fapi/v1/openInterest", params={"symbol": symbol})
        return float(d.get("openInterest"))
    except Exception:
        return None


def get_long_short_ratio(symbol: str, period: str = "5m", limit: int = 1) -> Optional[float]:
    try:
        d = _req(f"{BASE}/futures/data/globalLongShortAccountRatio", params={"symbol": symbol, "period": period, "limit": limit})
        if not d:
            return None
        last = d[-1]
        return float(last.get("longShortRatio"))
    except Exception:
        return None


def get_depth(symbol: str, limit: int = 5) -> dict:
    d = _req(f"{BASE}/fapi/v1/depth", params={"symbol": symbol, "limit": limit})
    bids = [(float(p), float(q)) for p, q in d.get("bids", [])[:limit]]
    asks = [(float(p), float(q)) for p, q in d.get("asks", [])[:limit]]
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


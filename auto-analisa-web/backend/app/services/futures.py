from __future__ import annotations
from typing import Optional, Dict, Any
import os, time
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import FuturesSignalsCache


BINANCE_FAPI = "https://fapi.binance.com"


async def _http_get_json(url: str, params: dict | None = None) -> dict | None:
    timeout = float(os.getenv("HTTP_TIMEOUT_S", "6"))
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def _norm_symbol(sym: str) -> str:
    s = sym.upper().replace(":USDT", "USDT").replace("/", "")
    if s.endswith("USDT"):
        return s
    return s + "USDT"


async def fetch_funding_basis(symbol: str) -> dict | None:
    """Fetch funding now/next/time and basis (mark-index) from premiumIndex.
    Returns { funding_now, next_funding_time, index_price, mark_price, basis_now }
    """
    if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    sym = _norm_symbol(symbol)
    url = f"{BINANCE_FAPI}/fapi/v1/premiumIndex"
    data = await _http_get_json(url, params={"symbol": sym})
    if not data or "markPrice" not in data or "indexPrice" not in data:
        return None
    try:
        mark = float(data.get("markPrice"))
        index = float(data.get("indexPrice"))
        basis = mark - index
        fr_now = float(data.get("lastFundingRate")) if data.get("lastFundingRate") is not None else None
        nft = int(data.get("nextFundingTime")) if data.get("nextFundingTime") is not None else None
        nft_iso = datetime.fromtimestamp(nft/1000.0, tz=timezone.utc).isoformat() if nft else None
        return {"funding_now": fr_now, "next_funding_time": nft_iso, "mark_price": mark, "index_price": index, "basis_now": basis}
    except Exception:
        return None


async def fetch_open_interest(symbol: str) -> float | None:
    if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    sym = _norm_symbol(symbol)
    url = f"{BINANCE_FAPI}/fapi/v1/openInterest"
    data = await _http_get_json(url, params={"symbol": sym})
    try:
        return float(data.get("openInterest")) if data and data.get("openInterest") is not None else None
    except Exception:
        return None


async def fetch_long_short_ratio(symbol: str, interval: str = "5m") -> dict | None:
    """Ambil global long/short account ratio (approx). Returns {accounts, positions} if available.
    Catatan: endpoint bisa berubah; jika gagal, kembalikan None.
    """
    if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    sym = _norm_symbol(symbol)
    # Accounts ratio
    url_acc = f"{BINANCE_FAPI}/futures/data/globalLongShortAccountRatio"
    acc = await _http_get_json(url_acc, params={"symbol": sym, "period": interval, "limit": 1})
    # Positions ratio
    url_pos = f"{BINANCE_FAPI}/futures/data/globalLongShortPositionRatio"
    pos = await _http_get_json(url_pos, params={"symbol": sym, "period": interval, "limit": 1})
    try:
        a = float(acc[0]["longShortRatio"]) if isinstance(acc, list) and acc else None
    except Exception:
        a = None
    try:
        p = float(pos[0]["longShortRatio"]) if isinstance(pos, list) and pos else None
    except Exception:
        p = None
    if a is None and p is None:
        return None
    return {"accounts": a, "positions": p}


async def fetch_taker_delta(symbol: str, interval: str = "5m") -> float | None:
    """Ambil taker buy/sell volume ratio lalu turunkan delta sederhana (buy - sell)/(buy+sell)."""
    if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    sym = _norm_symbol(symbol)
    url = f"{BINANCE_FAPI}/futures/data/takerlongshortRatio"
    data = await _http_get_json(url, params={"symbol": sym, "interval": interval, "limit": 1})
    try:
        if isinstance(data, list) and data:
            last = data[0]
            buy = float(last.get("buyVol", 0.0))
            sell = float(last.get("sellVol", 0.0))
            tot = buy + sell
            return ((buy - sell) / tot) if tot > 0 else 0.0
    except Exception:
        pass
    return None


async def fetch_oi_hist_delta(symbol: str, period: str = "1h") -> float | None:
    """Delta OI untuk periode terakhir (period=1h/4h)."""
    if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    sym = _norm_symbol(symbol)
    url = f"{BINANCE_FAPI}/futures/data/openInterestHist"
    data = await _http_get_json(url, params={"symbol": sym, "period": period, "limit": 2})
    try:
        if isinstance(data, list) and len(data) >= 2:
            v0 = float(data[-2]["sumOpenInterest"])  # previous
            v1 = float(data[-1]["sumOpenInterest"])   # latest
            return v1 - v0
    except Exception:
        pass
    return None


async def fetch_orderbook_metrics(symbol: str) -> dict | None:
    """Spread (bp), depth10bp bid/ask, imbalance dari snapshot orderbook (limit 100)."""
    if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    sym = _norm_symbol(symbol)
    url = f"{BINANCE_FAPI}/fapi/v1/depth"
    data = await _http_get_json(url, params={"symbol": sym, "limit": 100})
    try:
        bids = [(float(p), float(q)) for p, q in (data.get("bids") or [])]
        asks = [(float(p), float(q)) for p, q in (data.get("asks") or [])]
        if not bids or not asks:
            return None
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid = (best_bid + best_ask) / 2.0
        spread_bp = ((best_ask - best_bid) / mid) * 10000.0 if mid > 0 else None
        tol = mid * 0.001  # ±10bp
        depth_bid = sum(q for p, q in bids if p >= mid - tol)
        depth_ask = sum(q for p, q in asks if p <= mid + tol)
        imb = (depth_bid - depth_ask) / (depth_bid + depth_ask) if (depth_bid + depth_ask) > 0 else 0.0
        return {"spread_bp": spread_bp, "depth10bp_bid": depth_bid, "depth10bp_ask": depth_ask, "ob_imbalance": imb}
    except Exception:
        return None


async def fetch_leverage_bracket(symbol: str) -> dict | None:
    """Ambil leverage bracket: kembalikan mmr bracket pertama dan lev_max bila tersedia.
    Struktur Binance biasanya memuat 'brackets': [{ initialLeverage, maintMarginRatio, ... }].
    """
    if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    sym = _norm_symbol(symbol)
    url = f"{BINANCE_FAPI}/fapi/v1/leverageBracket"
    data = await _http_get_json(url, params={"symbol": sym})
    try:
        if isinstance(data, list) and data:
            br = data[0].get("brackets") or []
            if br:
                mmr = float(br[0].get("maintMarginRatio") or 0.0)
                levs = []
                try:
                    levs = [int(b.get("initialLeverage")) for b in br if b.get("initialLeverage") is not None]
                except Exception:
                    levs = []
                lev_max = max(levs) if levs else None
                return {"mmr": mmr, "lev_max": lev_max}
    except Exception:
        pass
    return None


async def refresh_signals_cache(db: AsyncSession, symbol: str) -> FuturesSignalsCache:
    sym = symbol.upper()
    fb = await fetch_funding_basis(sym) or {}
    oi = await fetch_open_interest(sym)
    lsr = await fetch_long_short_ratio(sym) or {}
    td5 = await fetch_taker_delta(sym, "5m")
    td15 = await fetch_taker_delta(sym, "15m")
    tdh1 = await fetch_taker_delta(sym, "1h")
    # delta OI dan orderbook metrics
    d1 = None
    oi_h1 = await fetch_oi_hist_delta(sym, "1h")
    oi_h4 = await fetch_oi_hist_delta(sym, "4h")
    ob = await fetch_orderbook_metrics(sym) or {}
    # basis bp
    try:
        basis_bp = (float(fb.get("basis_now")) / float(fb.get("index_price"))) * 10000.0 if fb.get("index_price") else None
    except Exception:
        basis_bp = None

    row = FuturesSignalsCache(
        symbol=sym,
        funding_now=fb.get("funding_now"),
        funding_next=None,  # not provided by endpoint; left None
        next_funding_time=fb.get("next_funding_time"),
        oi_now=oi,
        oi_d1=d1,
        oi_delta_h1=oi_h1,
        oi_delta_h4=oi_h4,
        lsr_accounts=lsr.get("accounts"),
        lsr_positions=lsr.get("positions"),
        basis_now=fb.get("basis_now"),
        basis_bp=basis_bp,
        taker_delta_m5=td5,
        taker_delta_m15=td15,
        taker_delta_h1=tdh1,
        spread_bp=ob.get("spread_bp"),
        depth10bp_bid=ob.get("depth10bp_bid"),
        depth10bp_ask=ob.get("depth10bp_ask"),
        ob_imbalance=ob.get("ob_imbalance"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def latest_signals(db: AsyncSession, symbol: str) -> dict:
    from sqlalchemy import desc
    q = await db.execute(select(FuturesSignalsCache).where(FuturesSignalsCache.symbol == symbol.upper()).order_by(desc(FuturesSignalsCache.created_at)))
    r = q.scalars().first()
    if not r:
        return {"has_data": False}
    return {
        "has_data": True,
        "symbol": r.symbol,
        "funding": {"now": r.funding_now, "next": r.funding_next, "time": r.next_funding_time},
        "oi": {"now": r.oi_now, "d1": r.oi_d1, "h1": getattr(r, "oi_delta_h1", None), "h4": getattr(r, "oi_delta_h4", None)},
        "lsr": {"accounts": r.lsr_accounts, "positions": r.lsr_positions},
        "basis": {"now": r.basis_now, "bp": getattr(r, "basis_bp", None)},
        "taker_delta": {"m5": r.taker_delta_m5, "m15": r.taker_delta_m15, "h1": r.taker_delta_h1},
        "orderbook": {"spread_bp": getattr(r, "spread_bp", None), "depth10bp_bid": getattr(r, "depth10bp_bid", None), "depth10bp_ask": getattr(r, "depth10bp_ask", None), "imbalance": getattr(r, "ob_imbalance", None)},
        "created_at": r.created_at,
    }

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


async def refresh_signals_cache(db: AsyncSession, symbol: str) -> FuturesSignalsCache:
    sym = symbol.upper()
    fb = await fetch_funding_basis(sym) or {}
    oi = await fetch_open_interest(sym)
    # Note: long/short ratio & taker delta not fetched (kept None in skeleton)
    row = FuturesSignalsCache(
        symbol=sym,
        funding_now=fb.get("funding_now"),
        funding_next=None,  # not provided by endpoint; left None
        next_funding_time=fb.get("next_funding_time"),
        oi_now=oi,
        oi_d1=None,
        lsr_accounts=None,
        lsr_positions=None,
        basis_now=fb.get("basis_now"),
        taker_delta_m5=None,
        taker_delta_m15=None,
        taker_delta_h1=None,
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
        "oi": {"now": r.oi_now, "d1": r.oi_d1},
        "lsr": {"accounts": r.lsr_accounts, "positions": r.lsr_positions},
        "basis": {"now": r.basis_now},
        "taker_delta": {"m5": r.taker_delta_m5, "m15": r.taker_delta_m15, "h1": r.taker_delta_h1},
        "created_at": r.created_at,
    }


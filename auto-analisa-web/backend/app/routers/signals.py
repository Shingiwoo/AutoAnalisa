from fastapi.routing import APIRouter
from fastapi import Query
from typing import List, Optional, Literal
from ..services.signal_mtf import calc_symbol_signal, compute_btc_bias, compute_signals_bulk, compute_btc_bias_json

router = APIRouter(prefix="/api", tags=["signals"]) 


@router.get("/mtf-signals")
@router.get("/signals")
async def get_mtf_signals(
    mode: Literal["fast", "medium", "swing"] = Query("medium"),
    symbols: str = Query("BTCUSDT,ETHUSDT"),
    market: str = Query("futures"),
    preset: str | None = Query(None),
    tau_entry: float | None = Query(None),
    alpha: float | None = Query(None),
    strict_bias: bool | None = Query(None),
):
    syms: List[str] = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return await compute_signals_bulk(
        syms, mode, preset=preset, tau_entry=tau_entry, alpha=alpha, strict_bias=strict_bias, market_type=market
    )


@router.get("/mtf-signals/{symbol}")
@router.get("/signals/{symbol}")
async def get_mtf_signal_symbol(
    symbol: str,
    mode: Literal["fast", "medium", "swing"] = Query("medium"),
    market: str = Query("futures"),
    preset: str | None = Query(None),
    tau_entry: float | None = Query(None),
    alpha: float | None = Query(None),
    strict_bias: bool | None = Query(None),
):
    return await calc_symbol_signal(symbol.upper(), mode, market_type=market, preset=preset, tau_entry=tau_entry, alpha=alpha, strict_bias=strict_bias)


@router.get("/mtf-signals/btc-bias")
@router.get("/signals/btc-bias")
async def get_btc_bias(
    mode: Literal["fast", "medium", "swing"] = Query("medium"),
    market: str = Query("futures"),
):
    return await compute_btc_bias_json(mode, market_type=market)

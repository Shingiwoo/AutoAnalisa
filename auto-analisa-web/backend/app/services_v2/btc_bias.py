from __future__ import annotations

from typing import Optional, Tuple
import pandas as pd

from app.services.market import fetch_klines
from app.services.indicators import rsi as rsi14


def _map_rsi_to_bias(rsi_value: float) -> str:
    if rsi_value >= 70:
        return "bullish_overbought"
    if rsi_value >= 55:
        return "bullish_cooling"
    if rsi_value >= 45:
        return "neutral"
    return "bearish_mild"


async def infer_btc_bias_from_exchange(
    symbol: str = "BTCUSDT", timeframe: str = "1h", limit: int = 320
) -> Tuple[Optional[str], dict]:
    """Fetch BTC OHLCV and derive bias from RSI(14) on the latest bar.

    Returns (bias_enum_or_none, context_dict), where context contains rsi_h1 and last_price.
    On any failure, returns (None, {}).
    """
    try:
        df = await fetch_klines(symbol, timeframe, limit, market="spot")
        if df is None or df.empty:
            return None, {}
        # Ensure numeric and compute RSI
        close = pd.to_numeric(df["close"], errors="coerce").fillna(method="ffill").fillna(method="bfill")
        rsi_series = rsi14(close, 14)
        last_rsi = float(rsi_series.iloc[-1])
        last_price = float(pd.to_numeric(df["close"].iloc[-1], errors="coerce"))
        bias = _map_rsi_to_bias(last_rsi)
        ctx = {"rsi_h1": last_rsi, "price": last_price}
        return bias, ctx
    except Exception:
        return None, {}


from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Candle(BaseModel):
    ts: int  # epoch ms
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorSet(BaseModel):
    ema5: Optional[float] = None
    ema10: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema100: Optional[float] = None
    ema200: Optional[float] = None
    rsi14: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bb_up: Optional[float] = None
    bb_mid: Optional[float] = None
    bb_low: Optional[float] = None


class MarketSnapshot(BaseModel):
    symbol: str = Field(..., examples=["BTCUSDT", "ETHUSDT", "XRPUSDT"])
    timeframe: Literal["15m", "1h", "4h", "1d"]
    last_price: float
    candles: List[Candle]
    indicators: IndicatorSet


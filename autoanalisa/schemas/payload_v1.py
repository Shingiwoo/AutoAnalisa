from __future__ import annotations

from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class Precision(BaseModel):
    price: float = Field(default=0.0001)
    qty: float = Field(default=0.1)
    min_notional: float = Field(default=5.0)


class Fees(BaseModel):
    maker: float
    taker: float


class Account(BaseModel):
    balance_usdt: Optional[float] = None
    fee_maker: Optional[float] = None
    fee_taker: Optional[float] = None
    risk_per_trade: float = 0.01
    leverage: Optional[int] = None
    margin_mode: Optional[Literal["cross", "isolated"]] = None


class BB(BaseModel):
    period: int
    mult: int
    upper: float
    middle: float
    lower: float


class MACDVals(BaseModel):
    dif: float
    dea: float
    hist: float


class TFIndicators(BaseModel):
    last: float
    open: float
    high: float
    low: float
    close_time: str
    ema: Dict[str, float]
    bb: BB
    rsi: Dict[str, float]
    stochrsi: Dict[str, float]
    macd: MACDVals
    atr14: float
    vol_last: float
    vol_ma5: float
    vol_ma10: float
    # Optional recent series to help rules detect patterns
    rsi6_last5: Optional[list[float]] = None
    close_last5: Optional[list[float]] = None
    ema50_last5: Optional[list[float]] = None


class StructureTF(BaseModel):
    trend: Literal["up", "down", "side"]
    hh: Optional[float] = None
    hl: Optional[float] = None
    lh: Optional[float] = None
    ll: Optional[float] = None


class LevelsTF(BaseModel):
    support: List[float] = Field(default_factory=list)
    resistance: List[float] = Field(default_factory=list)


class LevelsContainer(BaseModel):
    model_config = ConfigDict(extra="allow")
    confluence: Optional[List[dict]] = None


class Derivatives(BaseModel):
    funding_rate: Optional[float] = None
    next_funding_ts: Optional[str] = None
    oi: Optional[float] = None
    long_short_ratio: Optional[float] = None
    mark_price: Optional[float] = None
    index_price: Optional[float] = None
    basis_bp: Optional[float] = None


class Orderbook(BaseModel):
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    ob_imbalance_5: Optional[float] = None


class PayloadV1(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meta: Dict[str, str]
    symbol: str
    exchange: str
    market: Literal["spot", "futures"]
    contract: Literal["perp", "delivery"]
    timezone: str
    precision: Precision
    fees: Fees
    account: Account
    tf: Dict[str, TFIndicators]
    structure: Dict[str, StructureTF]
    levels: LevelsContainer
    derivatives: Optional[Derivatives] = None
    orderbook: Optional[Orderbook] = None
    orderflow: Optional[dict] = None
    news: Optional[list] = None
    session_bias: Optional[str] = None
    btc_bias: Optional[str] = None
    dxy_bias: Optional[str] = None
    insufficient_history: Optional[bool] = None
    notes: Optional[str] = None

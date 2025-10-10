from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class Level(BaseModel):
    label: str
    price: float


class TradePlan(BaseModel):
    bias: str = Field(description="bullish/bearish/neutral")
    entries: List[Level]
    take_profits: List[Level]
    stop_loss: Level
    rationale: str
    timeframe_alignment: List[str] = Field(description="timeframes yg sejalan")
    risk_note: Optional[str] = None


class LlmOutput(BaseModel):
    symbol: str
    timeframe: str
    profile: Optional[Literal["scalp", "swing", "auto"]] = None
    structure: str  # uptrend/downtrend/range
    momentum: str  # strong/weak/neutral
    key_levels: List[Level]
    plan: TradePlan
    # optional risk summary for profile constraints
    risk: Optional[dict] = Field(default=None, description="{ rr_min: float, sl_buf_atr: float, tp_atr: List[float], ttl_min: List[int] }")
    btc_bias_used: Optional[str] = None
    btc_alignment: Optional[Literal["aligned", "conflict", "neutral"]] = None

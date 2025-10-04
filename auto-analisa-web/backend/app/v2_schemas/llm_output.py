from pydantic import BaseModel, Field
from typing import List, Optional


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
    structure: str  # uptrend/downtrend/range
    momentum: str  # strong/weak/neutral
    key_levels: List[Level]
    plan: TradePlan


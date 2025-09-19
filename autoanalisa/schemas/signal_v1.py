from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel


class Signal(BaseModel):
    symbol: str
    market: Literal["spot", "futures"]
    side: Literal["long", "short"]
    setup: str
    score: int
    entry_zone: List[float]
    invalid_level: float
    sl: float
    tp: List[str]
    tp_price: List[float]
    risk_per_trade: float
    position_sizing: dict
    notes: List[str] = []
    timeframe_confirmations: dict = {}


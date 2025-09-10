from pydantic import BaseModel
from typing import List, Tuple


class AnalyzeOptions(BaseModel):
    tf: Tuple[str, str, str] = ("4h", "1h", "15m")
    risk_pct: float = 0.008
    mode: str = "auto"  # auto|PB|BO


class PlanPayload(BaseModel):
    bias: str
    support: List[float]
    resistance: List[float]
    mode: str
    entries: List[float]
    weights: List[float]
    invalid: float
    tp: List[float]
    score: int
    narrative: str


class PlanOut(BaseModel):
    id: int
    user_id: str
    symbol: str
    version: int
    payload: PlanPayload
    created_at: str


class AnalyzeIn(BaseModel):
    symbol: str
    options: AnalyzeOptions = AnalyzeOptions()


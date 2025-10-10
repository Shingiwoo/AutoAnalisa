from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class Indicators(BaseModel):
    EMA: str | None = None
    MACD: str | None = None
    RSI: float | None = None


class TFBlock(BaseModel):
    bias: str = ""
    kondisi: str = ""
    support: List[float] = Field(default_factory=list)
    resistance: List[float] = Field(default_factory=list)
    indikator: Indicators = Field(default_factory=Indicators)


class StrategyScalp(BaseModel):
    mode: str
    timeframe: str
    entry_zone: List[float]
    take_profit: List[float]
    stop_loss: float
    leverage_saran: str
    alokasi_risiko_per_trade: str
    estimated_performance: Dict[str, float | str]
    catatan: str = ""


class StrategySwing(BaseModel):
    mode: str
    timeframe: str
    entry_zone_utama: List[float]
    add_on_konfirmasi: str
    take_profit: Dict[str, float]
    stop_loss: float
    leverage_saran: str
    alokasi_risiko_per_trade: str
    RR: str
    estimated_performance: Dict[str, float]
    estimasi_durasi_mencapai_target_hari: Dict[str, str]
    syarat_valid: List[str]


class AnalysisRichOutput(BaseModel):
    metadata: Dict[str, object]
    multi_timeframe: Dict[str, TFBlock]
    rangkuman: Dict[str, object]
    strategi: Dict[str, object]
    penjelasan_posisi: Dict[str, List[str]]
    fundamental_ringkas: Dict[str, object]
    risk_management: Dict[str, object]
    kesimpulan_akhir: Dict[str, object]
    performansi_target: Dict[str, Dict[str, float]]
    disclaimer: str = ""


from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class TradeJournalIn(BaseModel):
    entry_at: str
    exit_at: Optional[str] = None
    saldo_awal: Optional[float] = None
    margin: Optional[float] = None
    leverage: Optional[float] = None
    sisa_saldo: Optional[float] = None
    pair: str
    arah: str
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    sl_price: Optional[float] = None
    be_price: Optional[float] = None
    tp1_price: Optional[float] = None
    tp2_price: Optional[float] = None
    tp3_price: Optional[float] = None
    tp1_status: Optional[str] = None
    tp2_status: Optional[str] = None
    tp3_status: Optional[str] = None
    sl_status: Optional[str] = None
    be_status: Optional[str] = None
    risk_reward: Optional[str] = None
    winloss: Optional[str] = None
    pnl_pct: Optional[float] = None
    equity_balance: Optional[float] = None
    strategy: Optional[str] = None
    market_condition: Optional[str] = None
    notes: Optional[str] = None
    open_qty: Optional[float] = 1.0
    status: Optional[str] = None


class TradeJournalOut(BaseModel):
    id: int
    entry_at: str
    exit_at: Optional[str]
    saldo_awal: Optional[float]
    margin: Optional[float]
    leverage: Optional[float]
    sisa_saldo: float
    pair: str
    arah: str
    entry_price: Optional[float]
    exit_price: Optional[float]
    sl_price: Optional[float]
    be_price: Optional[float]
    tp1_price: Optional[float]
    tp2_price: Optional[float]
    tp3_price: Optional[float]
    tp1_status: str
    tp2_status: str
    tp3_status: str
    sl_status: str
    be_status: str
    risk_reward: Optional[str]
    winloss: str
    pnl_pct: float
    equity_balance: Optional[float]
    strategy: Optional[str]
    market_condition: Optional[str]
    notes: str
    open_qty: float
    status: str
    created_at: str
    updated_at: str


class TradeJournalFilter(BaseModel):
    pair: Optional[str] = None
    status: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    page: int = 1
    limit: int = 50


from __future__ import annotations

import numpy as np
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange


def _ema(df: pd.DataFrame, period: int) -> float:
    return float(EMAIndicator(close=df["close"], window=period, fillna=False).ema_indicator().iloc[-1])


def ema_dict(df: pd.DataFrame, periods=(13, 20, 50, 100, 200)) -> dict:
    return {str(p): _ema(df, p) for p in periods}


def bb_dict(df: pd.DataFrame, period: int = 20, mult: int = 2) -> dict:
    bb = BollingerBands(close=df["close"], window=period, window_dev=mult, fillna=False)
    return {
        "period": period,
        "mult": mult,
        "upper": float(bb.bollinger_hband().iloc[-1]),
        "middle": float(bb.bollinger_mavg().iloc[-1]),
        "lower": float(bb.bollinger_lband().iloc[-1]),
    }


def rsi_dict(df: pd.DataFrame, periods=(6, 14, 25)) -> dict:
    out = {}
    for p in periods:
        out[str(p)] = float(RSIIndicator(close=df["close"], window=p, fillna=False).rsi().iloc[-1])
    return out


def stochrsi_dict(df: pd.DataFrame, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> dict:
    # Use StochasticOscillator on RSI proxy via high/low/close – approximated by using close as high/low if not present
    # Prefer: compute stochastic on close series as simplification; acceptable for MVP
    so = StochasticOscillator(high=df["high"], low=df["low"], close=df["close"], window=period, smooth_window=smooth_k)
    k = float(so.stoch().rolling(smooth_k).mean().iloc[-1])
    d = float(so.stoch_signal().rolling(smooth_d).mean().iloc[-1])
    return {"k": k, "d": d}


def macd_dict(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    macd = MACD(close=df["close"], window_slow=slow, window_fast=fast, window_sign=signal)
    return {
        "dif": float(macd.macd().iloc[-1]),
        "dea": float(macd.macd_signal().iloc[-1]),
        "hist": float(macd.macd_diff().iloc[-1]),
    }


def atr_last(df: pd.DataFrame, period: int = 14) -> float:
    atr = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=period, fillna=False)
    return float(atr.average_true_range().iloc[-1])


def volume_stats(df: pd.DataFrame, windows=(5, 10)) -> dict:
    vol_last = float(df["volume"].iloc[-1])
    vol_ma5 = float(df["volume"].rolling(windows[0]).mean().iloc[-1])
    vol_ma10 = float(df["volume"].rolling(windows[1]).mean().iloc[-1])
    return {"vol_last": vol_last, "vol_ma5": vol_ma5, "vol_ma10": vol_ma10}


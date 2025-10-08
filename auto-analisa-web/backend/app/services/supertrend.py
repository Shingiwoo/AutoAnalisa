from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Tuple
import numpy as np
import pandas as pd

# Lightweight, TV-parity Supertrend for batch and simple realtime

SrcType = Literal["close", "hl2", "ohlc4"]


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    return np.maximum(tr1, np.maximum(tr2, tr3))


def _rma(x: np.ndarray, length: int) -> np.ndarray:
    r = np.empty_like(x, dtype=float)
    r[:] = np.nan
    if len(x) == 0 or length <= 0:
        return r
    if len(x) < length:
        seed = np.nanmean(x[: max(1, len(x))])
        r[0] = seed
        for i in range(1, len(x)):
            r[i] = (r[i - 1] * (length - 1) + x[i]) / length
        return r
    sma0 = np.nanmean(x[:length])
    r[length - 1] = sma0
    for i in range(length, len(x)):
        r[i] = (r[i - 1] * (length - 1) + x[i]) / length
    return r


def _sma(x: np.ndarray, length: int) -> np.ndarray:
    if length <= 1:
        return x.astype(float)
    s = pd.Series(x, dtype="float64").rolling(length, min_periods=length).mean().to_numpy()
    return s


def _source(df: pd.DataFrame, kind: SrcType) -> np.ndarray:
    if kind == "close":
        return df["close"].to_numpy(dtype="float64")
    if kind == "hl2":
        return ((df["high"] + df["low"]) / 2.0).to_numpy(dtype="float64")
    if kind == "ohlc4":
        return ((df["open"] + df["high"] + df["low"] + df["close"]) / 4.0).to_numpy(dtype="float64")
    raise ValueError(f"Unknown source kind: {kind}")


@dataclass
class SupertrendResult:
    supertrend: pd.Series
    trend: pd.Series  # 1 up / -1 down
    signal: pd.Series  # 1 buy flip / -1 sell flip / 0 none
    up: pd.Series
    dn: pd.Series


def compute_supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
    src: SrcType = "hl2",
    change_atr: bool = True,
) -> SupertrendResult:
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        raise ValueError(f"DataFrame must contain columns {required}")

    h = df["high"].to_numpy(dtype="float64")
    l = df["low"].to_numpy(dtype="float64")
    c = df["close"].to_numpy(dtype="float64")
    s = _source(df, src)

    tr = _true_range(h, l, c)
    atr = _rma(tr, period) if change_atr else _sma(tr, period)

    up = s - multiplier * atr
    dn = s + multiplier * atr

    n = len(df)
    up_adj = np.full(n, np.nan, dtype="float64")
    dn_adj = np.full(n, np.nan, dtype="float64")
    trend = np.full(n, np.nan, dtype="float64")

    up_adj[0] = up[0]
    dn_adj[0] = dn[0]
    trend[0] = 1.0

    buy = np.zeros(n, dtype="int8")
    sell = np.zeros(n, dtype="int8")

    for i in range(1, n):
        up_prev = up_adj[i - 1]
        dn_prev = dn_adj[i - 1]

        up_raw = up[i]
        dn_raw = dn[i]

        up_now = np.maximum(up_raw, up_prev) if c[i - 1] > up_prev else up_raw
        dn_now = np.minimum(dn_raw, dn_prev) if c[i - 1] < dn_prev else dn_raw

        up_adj[i] = up_now
        dn_adj[i] = dn_now

        t_prev = trend[i - 1]
        t_now = t_prev
        if (t_prev == -1.0) and (c[i] > dn_prev):
            t_now = 1.0
        elif (t_prev == 1.0) and (c[i] < up_prev):
            t_now = -1.0
        trend[i] = t_now

        if (t_now == 1.0) and (t_prev == -1.0):
            buy[i] = 1
        elif (t_now == -1.0) and (t_prev == 1.0):
            sell[i] = -1

    supertrend = np.where(trend == 1.0, up_adj, dn_adj)

    out = pd.DataFrame(
        {
            "supertrend": supertrend,
            "trend": trend.astype("int8"),
            "signal": (buy + sell).astype("int8"),
            "up": up_adj,
            "dn": dn_adj,
        },
        index=df.index,
    )

    return SupertrendResult(
        supertrend=out["supertrend"],
        trend=out["trend"],
        signal=out["signal"],
        up=out["up"],
        dn=out["dn"],
    )


@dataclass
class SupertrendState:
    period: int
    multiplier: float
    change_atr: bool
    src: SrcType
    last_close: float
    last_up: float
    last_dn: float
    last_trend: int
    atr_prev: float
    sma_window: Optional[int] = None
    tr_sum: float = 0.0
    tr_queue: Optional[list] = None
    warmed: bool = False


def warmup_state(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
    src: SrcType = "hl2",
    change_atr: bool = True,
) -> SupertrendState:
    res = compute_supertrend(df, period=period, multiplier=multiplier, src=src, change_atr=change_atr)
    last_row = df.iloc[-1]
    # Infer last ATR from components
    mid = (last_row["high"] + last_row["low"]) / 2.0 if src == "hl2" else last_row["close"]
    inferred_atr = (res.up.iloc[-1] - mid) / -multiplier
    return SupertrendState(
        period=period,
        multiplier=multiplier,
        change_atr=change_atr,
        src=src,
        last_close=float(last_row["close"]),
        last_up=float(res.up.iloc[-1]),
        last_dn=float(res.dn.iloc[-1]),
        last_trend=int(res.trend.iloc[-1]),
        atr_prev=float(inferred_atr),
        sma_window=None,
        tr_sum=0.0,
        tr_queue=[],
        warmed=True,
    )


def update_realtime(
    state: SupertrendState, o: float, h: float, l: float, c: float
) -> Tuple[int, float, float, float]:
    tr = max(h - l, abs(h - state.last_close), abs(l - state.last_close))

    if state.change_atr:
        atr_now = (state.atr_prev * (state.period - 1) + tr) / state.period
    else:
        q = state.tr_queue or []
        q.append(tr)
        if len(q) > state.period:
            q.pop(0)
        state.tr_queue = q
        atr_now = float(np.mean(q))

    if state.src == "close":
        s = c
    elif state.src == "hl2":
        s = (h + l) / 2.0
    else:
        s = (o + h + l + c) / 4.0

    up_raw = s - state.multiplier * atr_now
    dn_raw = s + state.multiplier * atr_now

    up_now = max(up_raw, state.last_up) if state.last_close > state.last_up else up_raw
    dn_now = min(dn_raw, state.last_dn) if state.last_close < state.last_dn else dn_raw

    trend_now = state.last_trend
    if (state.last_trend == -1) and (c > state.last_dn):
        trend_now = 1
    elif (state.last_trend == 1) and (c < state.last_up):
        trend_now = -1

    signal = 0
    if (trend_now == 1) and (state.last_trend == -1):
        signal = 1
    elif (trend_now == -1) and (state.last_trend == 1):
        signal = -1

    state.last_close = c
    state.last_up = up_now
    state.last_dn = dn_now
    state.last_trend = trend_now
    state.atr_prev = atr_now

    return signal, trend_now, up_now, dn_now



from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import math
import numpy as np
import pandas as pd

from .rules import Features, make_levels
from .rounding import round_futures_prices
from .validator_futures import compute_rr_min_futures
from .filters_futures import gating_signals_ok

# --- Core helpers ---------------------------------------------------------

def _atr(df: pd.DataFrame, period: int = 14) -> float:
    high = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    close = df["close"].astype(float).to_numpy()
    tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    if len(tr) < period:
        return float(np.nanmean(tr)) if len(tr) else 0.0
    return float(pd.Series(tr).rolling(period).mean().iloc[-1])

def _last(df: pd.DataFrame, col: str) -> float:
    return float(df[col].iloc[-1])

def _ema_stack_ok(bundle: Dict[str, pd.DataFrame], side: str) -> bool:
    # Trend filter: 1H EMA20 vs EMA50, 4H EMA20 vs EMA50
    try:
        e1_20 = float(bundle["1h"]["ema20"].iloc[-1])
        e1_50 = float(bundle["1h"]["ema50"].iloc[-1])
        e4_20 = float(bundle["4h"]["ema20"].iloc[-1])
        e4_50 = float(bundle["4h"]["ema50"].iloc[-1])
    except Exception:
        return True  # don't block if indicators not present
    if side == "LONG":
        return e1_20 >= e1_50 and e4_20 >= e4_50
    else:
        return e1_20 <= e1_50 and e4_20 <= e4_50

def _levels_from_feature(feat: Features) -> Tuple[float, float, float, float]:
    lv = make_levels(feat)
    s1, s2 = float(lv["support"][0]), float(lv["support"][1])
    r1, r2 = float(lv["resistance"][0]), float(lv["resistance"][1])
    return s1, s2, r1, r2

# --- Public API -----------------------------------------------------------

def build_plan_futures(bundle: Dict[str, pd.DataFrame],
                       feat: Features,
                       side_hint: Optional[str] = None,
                       price_pad_bp: float = 8.0,
                       rr_min: float = 1.8,
                       fee_bp: float = 5.0,          # taker 0.05% default
                       slippage_bp: float = 2.0,     # conservative
                       use_llm_fixes: bool = False,
                       llm_fix_hook=None,
                       fut_signals: Optional[Dict[str, Any]] = None,
                       symbol: Optional[str] = None) -> Dict[str, Any]:
    """Return a plan dict suitable for validator_futures + FE overlay.

    Keys:
    - side: LONG/SHORT
    - entries: [e1, e2]
    - weights: [w1, w2]
    - invalids: {hard_1h: price}
    - tp: [ {name, range:[lo,hi]}, ... ]
    - notes: List[str]
    - gates: Dict[str, Any] (reasons, ok flags)
    - metrics: {rr_min, atr_pct, rr_raw}
    """
    side = (side_hint or "AUTO").upper()
    price = float(bundle["15m"]["close"].iloc[-1])

    # enrich / derive
    s1, s2, r1, r2 = _levels_from_feature(feat)
    atr15 = _atr(bundle["15m"], 14)
    atr_pct = (atr15 / price) * 100.0 if price > 0 else 0.0

    # Decide side if AUTO by trend + futures signals skew
    if side == "AUTO":
        long_bias = True
        try:
            long_bias = _ema_stack_ok(bundle, "LONG")
            if fut_signals:
                # Taker delta, OI and basis add/subtract bias
                td = float(fut_signals.get("taker_delta", {}).get("m15") or 0.0)
                oi = float(fut_signals.get("oi", {}).get("h1") or 0.0)
                basis_bp = float(fut_signals.get("basis", {}).get("bp") or 0.0)
                long_bias = long_bias and (td >= -0.05) and (oi >= -0.1) and (basis_bp >= -15.0)
        except Exception:
            pass
        side = "LONG" if long_bias else "SHORT"

    # Entries (pullback strategy to mid/ema) and invalid (beyond 1H swing)
    if side == "LONG":
        e1 = min(s1 + (price * price_pad_bp / 1e4), price)  # near support/MB/ema20
        e2 = min(s2 + (price * price_pad_bp * 0.5 / 1e4), e1 - max(0.25 * atr15, price * 5/1e4))
        invalid = s2 - max(atr15 * 0.8, price * 15/1e4)
        tp1 = max(r1 - max(0.25 * atr15, price * 5/1e4), price + 0.8 * atr15)
        tp2 = max(r2 - max(0.5 * atr15, price * 8/1e4), tp1 + 1.0 * atr15)
    else:  # SHORT
        e1 = max(r1 - (price * price_pad_bp / 1e4), price)
        e2 = max(r2 - (price * price_pad_bp * 0.5 / 1e4), e1 + max(0.25 * atr15, price * 5/1e4))
        invalid = r2 + max(atr15 * 0.8, price * 15/1e4)
        tp1 = min(s1 + max(0.25 * atr15, price * 5/1e4), price - 0.8 * atr15)
        tp2 = min(s2 + max(0.5 * atr15, price * 8/1e4), tp1 - 1.0 * atr15)

    weights = [0.4, 0.6]

    # Compute RR and auto-adjust invalid to satisfy rr_min (conservative)
    entries = [float(e1), float(e2)]
    tp_first = float(tp1)
    rr_now = compute_rr_min_futures(side, entries, tp_first, float(invalid), fee_bp, slippage_bp)
    # If RR below threshold, push invalid a bit farther and pull entries a bit better
    if rr_now < rr_min:
        k = max(1.0, rr_min / max(rr_now, 1e-6))
        if side == "LONG":
            invalid = invalid - 0.15 * k * atr15
            e1 = e1 - 0.08 * k * atr15
            e2 = e2 - 0.10 * k * atr15
        else:
            invalid = invalid + 0.15 * k * atr15
            e1 = e1 + 0.08 * k * atr15
            e2 = e2 + 0.10 * k * atr15
        entries = [float(e1), float(e2)]
        rr_now = compute_rr_min_futures(side, entries, tp_first, float(invalid), fee_bp, slippage_bp)

    # TP nodes with small ranges for FE
    tp = [
        {"name": "TP1", "range": [float(tp1), float(tp1 + (0.2 * atr15 if side == "LONG" else -0.2 * atr15))]},
        {"name": "TP2", "range": [float(tp2), float(tp2 + (0.3 * atr15 if side == "LONG" else -0.3 * atr15))]},
    ]

    plan = {
        "side": side,
        "entries": entries,
        "weights": weights,
        "invalids": {"hard_1h": float(invalid)},
        "tp": tp,
        "notes": [
            "Ambil partial 30–40% di TP1 lalu geser SL ke BE; sisanya trailing di bawah HL 15m (LONG) / di atas LH 15m (SHORT).",
            "Hindari entry ±15 menit sebelum/after funding setel; cek spread & orderbook imbalance.",
        ],
        "gates": {"checked": False, "ok": True, "reasons": []},
        "metrics": {"rr_min": float(rr_now), "atr_pct": float(atr_pct), "rr_raw": float(rr_now)},
    }

    # Round prices to futures tick using ccxt meta
    try:
        plan = round_futures_prices(symbol or "BTCUSDT", plan)
    except Exception:
        pass

    # Apply gating based on futures signals snapshot
    if fut_signals is not None:
        gates_ok, reasons, dumps = gating_signals_ok(side, fut_signals)
        plan["gates"] = {"checked": True, "ok": bool(gates_ok), "reasons": reasons, "snapshot": dumps}

    # Optional LLM fix pass (must return plan-like dict)
    if use_llm_fixes and callable(llm_fix_hook):
        try:
            plan = llm_fix_hook(plan, bundle=bundle, symbol=symbol)
        except Exception:
            # ignore LLM errors to keep deterministic plan
            pass

    return plan


from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import math
import numpy as np
import pandas as pd

from .rules import Features, make_levels, last5
from .rounding import round_futures_prices
from .validator_futures import compute_rr_min_futures
from .llm import ask_llm_messages
from .filters_futures import gating_signals_ok
from .utils_num import nearest_round, round_to_step

# --- Core helpers ---------------------------------------------------------

# Tunables for early patch rollout
SCORE_THRESHOLD = 60
USE_MACRO_GATING = False

PROFILE_CONFIG = {
    "scalp": {
        "ttl_min": 120,
        "atr_tf": "15m",
        "sl_atr": 0.45,
        "tp_multipliers": [1.0, 1.6],
        "tp_pct": [50, 50],
        "min_rr": 1.2,
        "entry_weights": [0.5, 0.5],
        "label": "Scalping",
    },
    "swing": {
        "ttl_min": 720,
        "atr_tf": "1h",
        "sl_atr": 0.8,
        "tp_multipliers": [2.0, 3.0],
        "tp_pct": [40, 60],
        "min_rr": 1.6,
        "entry_weights": [0.4, 0.6],
        "label": "Swing",
    },
}

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


def _swing_low(df: pd.DataFrame, lookback: int = 5) -> float | None:
    try:
        lows = df["low"].tail(lookback)
        return float(lows.min()) if len(lows) else None
    except Exception:
        return None


def _swing_high(df: pd.DataFrame, lookback: int = 5) -> float | None:
    try:
        highs = df["high"].tail(lookback)
        return float(highs.max()) if len(highs) else None
    except Exception:
        return None


def _range_15m(df15: pd.DataFrame, window: int = 48) -> tuple[float, float] | None:
    try:
        sl = df15.tail(window)
        return float(sl["low"].min()), float(sl["high"].max())
    except Exception:
        return None


def _round_number_near(price: float, symbol: str | None = None) -> float:
    """Nearest round number using tick-size-aware band when possible.
    Falls back to coarse 0.1/0.01 steps when tick is unavailable.
    """
    try:
        from .rounding import _tick_size_for  # reuse ccxt meta if online
        tick = _tick_size_for(symbol) if symbol else None
    except Exception:
        tick = None
    if tick and float(tick) > 0:
        return float(nearest_round(float(price), float(tick)))
    # fallback heuristic
    try:
        p = float(price)
        step = 0.1 if p >= 1 else 0.01
        return round(round(p / step) * step, 6)
    except Exception:
        return float(price)


def _candidate_plan(side: str, entries: List[float], invalid: float, tp: List[float], setup: str, notes: List[str]) -> Dict[str, Any]:
    return {
        "side": side,
        "entries": [float(entries[0]), float(entries[1] if len(entries) > 1 else entries[0])],
        "weights": [0.4, 0.6],
        "invalid": float(invalid),
        "tp": [float(tp[0]), float(tp[1] if len(tp) > 1 else tp[0])],
        "setup": setup,
        "notes": notes,
    }


def _make_setups(bundle: Dict[str, pd.DataFrame], feat: Features) -> List[Dict[str, Any]]:
    """Build L1–L3 (long) and S1–S3 (short) candidates from 5m/15m + 1h context.
    Returns list of candidate dicts or empty if none.
    """
    cands: List[Dict[str, Any]] = []
    df5 = bundle.get("5m") or bundle.get("15m")
    df15 = bundle.get("15m") or list(bundle.values())[0]
    df1 = bundle.get("1h") or df15
    price = float(df15.iloc[-1].close)
    atr15 = float(getattr(df15.iloc[-1], "atr14", 0.0) or 0.0)
    atr1h = float(getattr(df1.iloc[-1], "atr14", atr15) or atr15)
    ema50_15 = float(getattr(df15.iloc[-1], "ema50", price)) if "ema50" in df15.columns else price
    ema20_1h = float(getattr(df1.iloc[-1], "ema20", price)) if "ema20" in df1.columns else price
    ema50_1h = float(getattr(df1.iloc[-1], "ema50", price)) if "ema50" in df1.columns else price
    # L1 — Pullback ke EMA20 1H + Reclaim EMA50 15m (LONG)
    try:
        trend_up = (getattr(df1.iloc[-1], "ema20", ema20_1h) > getattr(df1.iloc[-1], "ema50", ema50_1h))
        trend_up = trend_up and (getattr(bundle.get("4h", df1).iloc[-1], "ema20", ema20_1h) >= getattr(bundle.get("4h", df1).iloc[-1], "ema50", ema50_1h))
        touch = abs(price - ema20_1h) <= 0.2 * atr1h
        reclaim = price > ema50_15
        if trend_up and touch and reclaim:
            sl = min(_swing_low(df15) or price - atr15, price - 0.8 * atr15)
            e1 = max(ema20_1h - 0.2 * atr1h, price - 0.6 * atr15)
            e2 = min(price, ema20_1h + 0.2 * atr1h)
            tp1 = price * 1.012 if price > 0 else price + 1.2 * atr15
            tp2 = price * 1.022 if price > 0 else price + 2.2 * atr15
            cands.append(_candidate_plan("LONG", [e1, e2], sl, [tp1, tp2], "L1", ["Reclaim EMA50 15m di zona EMA20 1H"]))
    except Exception:
        pass
    # L2 — Oversold Bounce + Divergence (LONG)
    try:
        if df5 is not None and "rsi6" in df5.columns:
            r6 = last5(df5["rsi6"]) or []
            lows5 = last5(df5["low"]) or []
            if r6 and lows5 and min(r6) < 20.0:
                # Simple higher low check
                if len(lows5) >= 3 and lows5[-1] > min(lows5[-3:]):
                    midbb5 = float(getattr(df5.iloc[-1], "mb", price)) if "mb" in df5.columns else price
                    e1 = min(price, midbb5)
                    e2 = min(price, price - 0.6 * (float(getattr(df5.iloc[-1], "atr14", atr15)) or atr15))
                    sl = min(_swing_low(df5) or price - atr15, price - 0.6 * atr15)
                    tp1, tp2 = price * 1.012, price * 1.022
                    cands.append(_candidate_plan("LONG", [e1, e2], sl, [tp1, tp2], "L2", ["RSI6 < 20 & bounce oversold"]))
    except Exception:
        pass
    # L3 — Rebreak Range High 15m + Retest (LONG)
    try:
        rng = _range_15m(df15, 64)
        if rng:
            lo, hi = rng
            if price > hi * 1.001:  # close above range
                e1 = hi
                e2 = hi + 0.1 * atr15
                sl = hi - 0.7 * atr15
                tp1, tp2 = price * 1.012, price * 1.022
                cands.append(_candidate_plan("LONG", [e1, e2], sl, [tp1, tp2], "L3", ["Rebreak RH 15m & retest"]))
    except Exception:
        pass
    # S1 — Breakdown & Retest Gagal EMA50 15m (SHORT)
    try:
        below = price < ema50_15
        near = abs(price - ema50_15) <= 0.1 * atr15
        macd_hist_5m = float(getattr(df5.iloc[-1], "hist", 0.0)) if (df5 is not None and "hist" in df5.columns) else 0.0
        if below and near and macd_hist_5m <= 0:
            e1 = max(price, ema50_15)
            e2 = e1 + 0.25 * atr15
            sl = max(_swing_high(df15) or price + atr15, e2 + 0.8 * atr15)
            tp1 = price * 0.983 if price > 0 else price - 0.017 * abs(price)
            tp2 = price * 0.97 if price > 0 else price - 0.03 * abs(price)
            cands.append(_candidate_plan("SHORT", [e1, e2], sl, [tp1, tp2], "S1", ["Retest gagal EMA50 15m; MACD melemah"]))
    except Exception:
        pass
    # S2 — Reject Cluster EMA20 1H (SHORT)
    try:
        ema10_1h = float(getattr(df1.iloc[-1], "ema20", ema20_1h))  # fallback ema20 as ema10 not available
        cl_low = min(ema10_1h, ema20_1h)
        cl_high = max(ema10_1h, ema20_1h)
        # Sweep above cluster then close back below
        if price < cl_low and (df15.iloc[-2].close if len(df15) >= 2 else price) > cl_low:
            e1 = cl_low
            e2 = cl_high
            sl = cl_high + 0.6 * atr15
            tp1 = price * 0.983
            tp2 = price * 0.97
            cands.append(_candidate_plan("SHORT", [e1, e2], sl, [tp1, tp2], "S2", ["Reject cluster EMA20 1H"]))
    except Exception:
        pass
    # S3 — False-Break Angka Bulat (SHORT)
    try:
        tick5 = None
        try:
            from .rounding import _tick_size_for
            tick5 = _tick_size_for(ctx_symbol) if (ctx_symbol := None) else None
        except Exception:
            tick5 = None
        rn = _round_number_near(price, symbol=None)
        # if we have tick, recompute rn precisely
        if tick5 and float(tick5) > 0:
            rn = float(nearest_round(price, float(tick5)))
        # RSI6 roll-down condition if available
        rsi_ok = True
        try:
            if "rsi6" in df5.columns and len(df5) >= 2:
                r_now = float(df5.iloc[-1].rsi6)
                r_prev = float(df5.iloc[-2].rsi6)
                rsi_ok = (r_prev > 70.0) and (r_now < r_prev)
        except Exception:
            rsi_ok = True
        # simple false-break check: high pierced rn but close back below rn
        if float(df5.iloc[-1].high) > rn and float(df5.iloc[-1].close) < rn and rsi_ok:
            atr5 = float(getattr(df5.iloc[-1], "atr14", atr15)) or atr15
            tol = max(0.1 * atr5, 2.0 * (float(tick5) if tick5 else 0.0))
            e1 = rn - 0.1 * atr5
            e2 = rn - 0.2 * atr5
            sl = rn + 0.6 * atr5
            # snap to tick if available
            if tick5 and float(tick5) > 0:
                e1 = round_to_step(e1, float(tick5))
                e2 = round_to_step(e2, float(tick5))
                sl = round_to_step(sl, float(tick5))
            tp1, tp2 = price * 0.983, price * 0.97
            cands.append(_candidate_plan("SHORT", [e1, e2], sl, [tp1, tp2], "S3", ["False-break angka bulat"]))
    except Exception:
        pass
    return [c for c in cands if c]


def score_candidate(c: Dict[str, Any], ctx: Dict[str, Any]) -> int:
    side = (c.get("side") or "LONG").upper()
    score = 0
    reasons: List[str] = []
    # Gating signals (funding/LSR/basis/taker/spread)
    ok, rs, _dump = gating_signals_ok(side, ctx.get("fut_signals") or {})
    if ok:
        score += 30
    else:
        reasons.extend(rs)
    # Confluence: proximity to EMA / ranges
    try:
        bundle = ctx.get("bundle") or {}
        df15 = bundle.get("15m")
        last = df15.iloc[-1] if df15 is not None and len(df15) else None
        ema50_15 = float(getattr(last, "ema50", 0.0)) if last is not None else 0.0
        ema20_1h = float(getattr((bundle.get("1h") or df15).iloc[-1], "ema20", 0.0)) if (bundle.get("1h") or df15) is not None else 0.0
        e_avg = sum(c.get("entries", []) or [0]) / max(1, len(c.get("entries", [])))
        d1 = abs(e_avg - ema50_15) / max(ema50_15, 1e-9) if ema50_15 else 1.0
        d2 = abs(e_avg - ema20_1h) / max(ema20_1h, 1e-9) if ema20_1h else 1.0
        near = 0
        near += 8 if d1 < 0.002 else (4 if d1 < 0.005 else 0)
        near += 7 if d2 < 0.003 else (3 if d2 < 0.006 else 0)
        score += near
    except Exception:
        pass
    # Structure alignment (trend filter)
    try:
        if _ema_stack_ok(ctx.get("bundle"), side):
            score += 15
        else:
            score -= 15
    except Exception:
        pass
    # Derivatif health bonus (basis/td/oi if present)
    try:
        sig = ctx.get("fut_signals") or {}
        basis_ok = ((sig.get("basis") or {}).get("bp") or 0.0) >= -15.0 if side == "LONG" else ((sig.get("basis") or {}).get("bp") or 0.0) <= 40.0
        td_ok = ((sig.get("taker_delta") or {}).get("m15") or 0.0) >= -0.05 if side == "LONG" else ((sig.get("taker_delta") or {}).get("m15") or 0.0) <= 0.08
        if basis_ok:
            score += 5
        if td_ok:
            score += 5
    except Exception:
        pass
    c["_reasons"] = reasons
    c["_score"] = int(score)
    return int(score)

# --- Public API -----------------------------------------------------------

def build_plan_futures(bundle: Dict[str, pd.DataFrame],
                       feat: Features,
                       side_hint: Optional[str] = None,
                       price_pad_bp: float = 8.0,
                       rr_min: float = 0.0,
                       fee_bp: float = 5.0,          # taker 0.05% default
                       slippage_bp: float = 2.0,     # conservative
                       use_llm_fixes: bool = False,
                       llm_fix_hook=None,
                       fut_signals: Optional[Dict[str, Any]] = None,
                       symbol: Optional[str] = None,
                       profile: str = "scalp") -> Dict[str, Any]:
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
    atr1h = _atr(bundle.get("1h", bundle["15m"]), 14)
    atr_pct = (atr15 / price) * 100.0 if price > 0 else 0.0

    profile_key = str(profile or "scalp").lower()
    cfg = PROFILE_CONFIG.get(profile_key, PROFILE_CONFIG["scalp"])
    rr_target = float(rr_min or cfg.get("min_rr", 1.2))
    atr_ref = atr15 if cfg.get("atr_tf") == "15m" else atr1h or atr15
    weights = list(cfg.get("entry_weights") or [0.4, 0.6])

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

    # Entries (pullback strategy to mid/ema) and invalid (beyond swing) menyesuaikan profil
    if side == "LONG":
        e1 = min(s1 + (price * price_pad_bp / 1e4), price)  # near support/MB/ema20
        e2 = min(s2 + (price * price_pad_bp * 0.5 / 1e4), e1 - max(0.25 * atr15, price * 5/1e4))
        invalid = min(e1, e2) - max(atr_ref * cfg.get("sl_atr", 0.45), atr15 * 0.3)
    else:  # SHORT
        e1 = max(r1 - (price * price_pad_bp / 1e4), price)
        e2 = max(r2 - (price * price_pad_bp * 0.5 / 1e4), e1 + max(0.25 * atr15, price * 5/1e4))
        invalid = max(e1, e2) + max(atr_ref * cfg.get("sl_atr", 0.45), atr15 * 0.3)

    # Compute RR and auto-adjust invalid to satisfy rr_min (conservative)
    entries = [float(e1), float(e2)]
    avg_entry = sum(entries) / len(entries)
    if side == "LONG":
        tp1 = avg_entry + cfg.get("tp_multipliers", [1.0, 1.6])[0] * atr_ref
        tp2 = avg_entry + cfg.get("tp_multipliers", [1.0, 1.6])[1] * atr_ref
    else:
        tp1 = avg_entry - cfg.get("tp_multipliers", [1.0, 1.6])[0] * atr_ref
        tp2 = avg_entry - cfg.get("tp_multipliers", [1.0, 1.6])[1] * atr_ref

    tp_first = float(tp1)
    rr_now = compute_rr_min_futures(side, entries, tp_first, float(invalid), fee_bp, slippage_bp)
    # If RR below threshold, push invalid a bit farther and pull entries a bit better
    if rr_now < rr_target:
        k = max(1.0, rr_target / max(rr_now, 1e-6))
        eps = max(abs(avg_entry) * 1e-5, atr_ref * 0.01, 1e-5)
        if side == "LONG":
            e1 = e1 - 0.08 * k * atr_ref
            e2 = e2 - 0.10 * k * atr_ref
            invalid = min(invalid + 0.20 * k * atr_ref, min(e1, e2) - eps)
        else:
            e1 = e1 + 0.08 * k * atr_ref
            e2 = e2 + 0.10 * k * atr_ref
            invalid = max(invalid - 0.20 * k * atr_ref, max(e1, e2) + eps)
        entries = [float(e1), float(e2)]
        rr_now = compute_rr_min_futures(side, entries, tp_first, float(invalid), fee_bp, slippage_bp)
        if rr_now < rr_target:
            avg_entry_adj = sum(entries) / len(entries)
            if side == "LONG":
                target_invalid = avg_entry_adj - (tp_first - avg_entry_adj) / rr_target
                invalid = min(target_invalid, min(entries) - eps)
            else:
                target_invalid = avg_entry_adj + (avg_entry_adj - tp_first) / rr_target
                invalid = max(target_invalid, max(entries) + eps)
            rr_now = compute_rr_min_futures(side, entries, tp_first, float(invalid), fee_bp, slippage_bp)

    # TP nodes with small ranges for FE
    tp = [
        {
            "name": "TP1",
            "range": [
                float(tp1),
                float(tp1 + (0.18 * atr_ref if side == "LONG" else -0.18 * atr_ref)),
            ],
            "reduce_only_pct": cfg.get("tp_pct", [50, 50])[0],
        },
        {
            "name": "TP2",
            "range": [
                float(tp2),
                float(tp2 + (0.25 * atr_ref if side == "LONG" else -0.25 * atr_ref)),
            ],
            "reduce_only_pct": cfg.get("tp_pct", [50, 50])[1],
        },
    ]

    plan = {
        "side": side,
        "entries": entries,
        "weights": weights,
        "invalids": {"hard_1h": float(invalid)},
        "tp": tp,
        "notes": [
            f"Profil {cfg.get('label')} ({cfg.get('atr_tf').upper()}): TTL {cfg.get('ttl_min')} menit; SL buffer {cfg.get('sl_atr'):.2f}×ATR.",
            "Setelah TP1 → geser SL ke BE lalu trailing di bawah HL 15m (LONG) / di atas LH 15m (SHORT).",
            "Periksa spread & orderbook; hindari entry ±15 menit sebelum/after funding.",
        ],
        "gates": {"checked": False, "ok": True, "reasons": []},
        "metrics": {
            "rr_min": float(rr_now),
            "atr_pct": float(atr_pct),
            "rr_raw": float(rr_now),
            "rr_target": rr_target,
        },
        "score": 0,
        "profile": profile_key,
        "profile_config": dict(cfg),
        "ttl_min": cfg.get("ttl_min"),
        "tp_pct": list(cfg.get("tp_pct", [50, 50])),
    }
    if profile_key == "scalp":
        plan.setdefault("notes", []).append("Ambil 50% reduce-only di TP1, sisanya TP2; fokus eksekusi cepat <150 menit.")
    else:
        plan.setdefault("notes", []).append("Ambil 40% di TP1 dan 60% di TP2; tahan posisi mengikuti struktur 1H/4H.")

    # Round prices to futures tick using ccxt meta and expose precision
    try:
        plan = round_futures_prices(symbol or "BTCUSDT", plan)
        # attach tick/step size to metrics if available
        from .rounding import precision_for
        prec = precision_for(symbol or "BTCUSDT") or {}
        plan.setdefault("metrics", {})
        if prec.get("tickSize") is not None:
            plan["metrics"]["tick_size"] = float(prec.get("tickSize"))
        if prec.get("stepSize") is not None:
            plan["metrics"]["step_size"] = float(prec.get("stepSize"))
    except Exception:
        pass

    # Apply gating based on futures signals snapshot
    if fut_signals is not None:
        # attach ATR/last for 1h to support ATR% gating
        try:
            last_1h = float(bundle["1h"].iloc[-1].close)
        except Exception:
            last_1h = None
        try:
            atr_1h = float(bundle["1h"].iloc[-1].atr14)
        except Exception:
            atr_1h = None
        sig2 = dict(fut_signals)
        if last_1h is not None:
            sig2["last_1h"] = last_1h
        if atr_1h is not None:
            sig2["atr_1h"] = atr_1h
        gates_ok, reasons, dumps = gating_signals_ok(side, sig2, profile=profile_key)
        plan["gates"] = {"checked": True, "ok": bool(gates_ok), "reasons": reasons, "snapshot": dumps}

    # Patch 3/4: Setup candidates (L1-L3/S1-S3) + scoring & conflict resolution
    try:
        cands = _make_setups(bundle, feat)
        if cands:
            ctx = {"bundle": bundle, "fut_signals": fut_signals or {}}
            for c in cands:
                c["score"] = score_candidate(c, ctx)
            # Pick best by score
            best = sorted(cands, key=lambda x: x.get("score", 0), reverse=True)
            top = best[0]
            # Conflict resolver: if two best are opposite sides and close score (<5), skip trade
            if len(best) >= 2 and (best[0].get("side") != best[1].get("side")) and abs(best[0].get("score", 0) - best[1].get("score", 0)) < 5:
                # mark no-trade by lowering weights and adding note
                plan.setdefault("notes", []).append("Resolver: kandidat berlawanan skor <5 → no-trade")
            elif top.get("score", 0) >= SCORE_THRESHOLD:
                # adopt candidate into plan while preserving FE shape
                side = top["side"]
                entries = [float(x) for x in (top.get("entries") or entries)]
                invalid = float(top.get("invalid", invalid))
                tp1, tp2 = float((top.get("tp") or [tp1, tp2])[0]), float((top.get("tp") or [tp1, tp2])[1] if len(top.get("tp") or []) > 1 else (tp2))
                weights = [0.4, 0.6]
                tp = [
                    {"name": "TP1", "range": [float(tp1), float(tp1 + (0.2 * atr15 if side == "LONG" else -0.2 * atr15))]},
                    {"name": "TP2", "range": [float(tp2), float(tp2 + (0.3 * atr15 if side == "LONG" else -0.3 * atr15))]},
                ]
                rr_now = compute_rr_min_futures(side, entries, float(tp1), float(invalid), fee_bp, slippage_bp)
                plan.update({
                    "side": side,
                    "entries": entries,
                    "weights": weights,
                    "invalids": {"hard_1h": float(invalid)},
                    "tp": tp,
                    "score": int(top.get("score", 0)),
                })
                plan.setdefault("metrics", {})["rr_min"] = float(rr_now)
                plan.setdefault("notes", []).append(f"Setup {top.get('setup')} skor {top.get('score')}")
                if top.get("notes"):
                    plan["notes"].extend(top.get("notes"))
                # Gating again with final side
                if fut_signals is not None:
                    sig2 = dict(fut_signals)
                    if last_1h is not None:
                        sig2["last_1h"] = last_1h
                    if atr_1h is not None:
                        sig2["atr_1h"] = atr_1h
                    gates_ok, reasons, dumps = gating_signals_ok(side, sig2, profile=profile_key)
                    plan["gates"] = {"checked": True, "ok": bool(gates_ok), "reasons": reasons, "snapshot": dumps}
    except Exception:
        pass

    # Optional LLM fix pass (must return plan-like dict)
    if use_llm_fixes:
        def _default_llm_fix_hook(p0: Dict[str, Any], *, bundle: Dict[str, pd.DataFrame], symbol: Optional[str] = None) -> Dict[str, Any]:
            """Best-effort LLM correction to improve RR while preserving structure.
            Expects JSON-only output: { entries: [..], tp: [{name,range:[..]},..], invalids:{hard_1h:..}, notes:[..] }
            """
            try:
                # Minimal snapshot for context
                def _safe(v, d=None):
                    try:
                        return float(v)
                    except Exception:
                        return d
                snap = {
                    "price": _safe(bundle["15m"].iloc[-1].close, None),
                    "ema": {
                        "1h": {"ema20": _safe(bundle["1h"].iloc[-1].ema20, None), "ema50": _safe(bundle["1h"].iloc[-1].ema50, None)},
                        "4h": {"ema20": _safe(bundle["4h"].iloc[-1].ema20, None), "ema50": _safe(bundle["4h"].iloc[-1].ema50, None)},
                    },
                    "atr15m": _safe(bundle["15m"].iloc[-1].atr14, None),
                }
                # Compose strict-JSON instruction
                import json as _json
                messages = [
                    {"role": "system", "content": "Anda asisten strategi Futures. Keluarkan hanya JSON valid (object)."},
                    {"role": "user", "content": (
                        "Tugas: Koreksi rencana Futures agar RR >= %.2f, jaga 2 entry & 2 TP.\n"
                        "Input: {\"snapshot_MTF\": %s, \"plan_awal\": %s, \"fee_bp\": %.3f, \"slippage_bp\": %.3f}\n"
                        "Output (JSON only): { \"entries\":[..], \"tp\":[{\"name\":\"TP1\",\"range\":[..]},{\"name\":\"TP2\",\"range\":[..]}], \"invalids\":{\"hard_1h\":..}, \"notes\":[..] }\n"
                        "Aturan: Naikkan RR tanpa memperburuk validitas teknikal; hindari TP menurun; bobot 0.4/0.6 dipertahankan."
                    ) % (
                        float(rr_min),
                        _json.dumps(snap, ensure_ascii=False),
                        _json.dumps(p0, ensure_ascii=False),
                        float(fee_bp), float(slippage_bp)
                    )},
                ]
                text, _usage = ask_llm_messages(messages)
                import json
                data = json.loads(text or "{}") if text else {}
                if not isinstance(data, dict) or not data:
                    return p0
                p1 = dict(p0)
                # attach usage for upstream accounting (router will log and strip if needed)
                try:
                    p1.setdefault("_usage", {})
                    p1["_usage"].update({
                        "prompt_tokens": int((_usage or {}).get("prompt_tokens") or 0),
                        "completion_tokens": int((_usage or {}).get("completion_tokens") or 0),
                        "total_tokens": int((_usage or {}).get("total_tokens") or 0),
                    })
                except Exception:
                    pass
                # Merge entries
                if isinstance(data.get("entries"), list) and len(data["entries"]) >= 2:
                    try:
                        e_nums = [float(x) for x in data["entries"][:2]]
                        p1["entries"] = e_nums
                    except Exception:
                        pass
                # Merge invalids.hard_1h
                inv = data.get("invalids") or {}
                try:
                    if inv and inv.get("hard_1h") is not None:
                        p1.setdefault("invalids", {})
                        p1["invalids"]["hard_1h"] = float(inv.get("hard_1h"))
                except Exception:
                    pass
                # Merge tp nodes
                if isinstance(data.get("tp"), list) and data["tp"]:
                    tps = []
                    for t in data["tp"][:2]:
                        try:
                            name = t.get("name") or f"TP{len(tps)+1}"
                            rng = t.get("range") or []
                            lo = float(rng[0]); hi = float(rng[1]) if len(rng) > 1 else lo
                            if lo is not None and hi is not None:
                                tps.append({"name": name, "range": [lo, hi]})
                        except Exception:
                            continue
                    if tps:
                        p1["tp"] = tps
                # Notes
                if isinstance(data.get("notes"), list):
                    try:
                        p1.setdefault("notes", [])
                        p1["notes"].extend([str(n) for n in data["notes"]][:4])
                    except Exception:
                        pass
                # Recompute RR; if still below threshold, keep original
                try:
                    e_nums = [float(x) for x in (p1.get("entries") or [])]
                    tp1v = float((p1.get("tp") or [{}])[0].get("range", [None])[0]) if (p1.get("tp") or [{}])[0].get("range") else None
                    inv_final = float((p1.get("invalids") or {}).get("hard_1h")) if (p1.get("invalids") or {}).get("hard_1h") is not None else None
                    rr_new = compute_rr_min_futures(p1.get("side") or "LONG", e_nums, tp1v, inv_final, fee_bp, slippage_bp)
                    p1.setdefault("metrics", {})
                    p1["metrics"]["rr_min"] = float(rr_new)
                    if rr_new >= float(rr_min):
                        return p1
                    # else, fallback to original but append note
                    p0 = dict(p0)
                    p0.setdefault("notes", []).append("LLM fixes diabaikan: RR masih di bawah ambang")
                    return p0
                except Exception:
                    return p1
            except Exception:
                return p0

        try:
            hook = llm_fix_hook if callable(llm_fix_hook) else _default_llm_fix_hook
            plan = hook(plan, bundle=bundle, symbol=symbol)
        except Exception:
            # ignore LLM errors to keep deterministic plan
            pass

    return plan

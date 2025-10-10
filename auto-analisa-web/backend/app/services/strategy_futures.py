
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

PROFILES = {
    "scalp": {
        "tf_exec": ["1m", "5m"],
        "tf_context": "15m",
        "min_rr": 1.2,
        "ttl_min": [90, 150],
        "sl_buf_atr": 0.4,
        "tp_atr": [1.0, 1.6],
        "tp_split": [0.5, 0.5],
        "avoid_news_min": 30,
        "vol_mult": 1.2,
        "label": "Scalping",
        "entry_weights": [0.5, 0.5],
    },
    "swing": {
        "tf_exec": ["15m", "1h"],
        "tf_context": "1h",
        "min_rr": 1.6,
        "ttl_min": [360, 1440],
        "sl_buf_atr": 0.8,
        "tp_atr": [2.0, 3.0],
        "tp_split": [0.4, 0.6],
        "avoid_news_min": 15,
        "vol_mult": 1.0,
        "label": "Swing",
        "entry_weights": [0.4, 0.6],
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


def _vol_snapshot(bundle: Dict[str, pd.DataFrame], prefer: Tuple[str, ...] = ("1m", "5m")) -> Tuple[float | None, float | None, str | None]:
    for tf in prefer:
        df = bundle.get(tf)
        if df is None or len(df) < 5:
            continue
        try:
            vol = df["volume"].astype(float)
            if len(vol) < 5:
                continue
            current = float(vol.iloc[-1])
            ma20 = float(vol.tail(20).mean()) if len(vol) >= 20 else float(vol.mean())
            return current, ma20, tf
        except Exception:
            continue
    return None, None, None


def _micro_swing_price(bundle: Dict[str, pd.DataFrame], side: str) -> float | None:
    try:
        if side == "LONG":
            lows: List[float] = []
            for tf in ("5m", "15m"):
                df = bundle.get(tf)
                if df is not None:
                    val = _swing_low(df, lookback=6)
                    if val is not None:
                        lows.append(float(val))
            return min(lows) if lows else None
        else:
            highs: List[float] = []
            for tf in ("5m", "15m"):
                df = bundle.get(tf)
                if df is not None:
                    val = _swing_high(df, lookback=6)
                    if val is not None:
                        highs.append(float(val))
            return max(highs) if highs else None
    except Exception:
        return None


def _tp_targets(side: str, avg_entry: float, atr: float, profile_cfg: Dict[str, Any]) -> Tuple[float, float]:
    mults = list(profile_cfg.get("tp_atr") or [1.0, 1.6])
    m1 = float(mults[0] if mults else 1.0)
    m2 = float(mults[1] if len(mults) > 1 else m1 * 1.5)
    if side == "LONG":
        return avg_entry + m1 * atr, avg_entry + m2 * atr
    return avg_entry - m1 * atr, avg_entry - m2 * atr


def _apply_sl_buffer(swing_price: float | None, side: str, atr: float, profile_cfg: Dict[str, Any]) -> float | None:
    if swing_price is None:
        return None
    buf = float(profile_cfg.get("sl_buf_atr", 0.4) or 0.0) * float(atr)
    if side == "LONG":
        return float(swing_price) - buf
    return float(swing_price) + buf


def _resolve_stop(entries: List[float], sl_seed: float | None, atr: float, price: float, side: str) -> float:
    buffer_edge = max(0.25 * atr, abs(price) * 1e-4)
    if side == "LONG":
        base = min(entries)
        fallback = base - max(0.6 * atr, abs(price) * 1e-4)
        sl_val = fallback if sl_seed is None else float(sl_seed)
        sl_val = min(sl_val, base - buffer_edge)
        if sl_val >= base:
            sl_val = base - buffer_edge
        return float(sl_val)
    base = max(entries)
    fallback = base + max(0.6 * atr, abs(price) * 1e-4)
    sl_val = fallback if sl_seed is None else float(sl_seed)
    sl_val = max(sl_val, base + buffer_edge)
    if sl_val <= base:
        sl_val = base + buffer_edge
    return float(sl_val)


def _candidate(side: str,
               entries: List[float],
               invalid: float,
               tp: List[float],
               setup: str,
               notes: List[str],
               vol_ok: bool = True,
               meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "side": side,
        "entries": [float(entries[0]), float(entries[1] if len(entries) > 1 else entries[0])],
        "invalid": float(invalid),
        "tp": [float(tp[0]), float(tp[1] if len(tp) > 1 else tp[0])],
        "setup": setup,
        "notes": list(notes or []),
        "vol_ok": bool(vol_ok),
        "meta": meta or {},
    }


def pick_by_rr_confluence(candidates: List[Dict[str, Any]],
                          min_rr: float,
                          fee_bp: float,
                          slippage_bp: float) -> Optional[Dict[str, Any]]:
    best: Optional[Dict[str, Any]] = None
    best_score = -1e9
    for cand in candidates:
        side = cand.get("side") or "LONG"
        entries = cand.get("entries") or []
        invalid = cand.get("invalid")
        tp_list = cand.get("tp") or []
        if not entries or invalid is None or not tp_list:
            continue
        tp1 = tp_list[0]
        rr = compute_rr_min_futures(side, entries, float(tp1), float(invalid), fee_bp, slippage_bp)
        cand["rr"] = rr
        score = rr * 10.0
        if not cand.get("vol_ok", True):
            score -= 5.0
        # Tambah sedikit bobot bila setup pullback / reclaim
        setup = str(cand.get("setup") or "")
        if "PB" in setup:
            score += 1.5
        if rr >= float(min_rr):
            score += 4.0
        if score > best_score:
            best_score = score
            best = cand
    return best


def _make_scalp_candidates(bundle: Dict[str, pd.DataFrame],
                           levels: Dict[str, Any],
                           profile_cfg: Dict[str, Any],
                           bias: str,
                           symbol: Optional[str],
                           vol_ok: bool,
                           fut_signals: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    df15 = bundle.get("15m")
    if df15 is None:
        df15 = next(iter(bundle.values()))
    df5 = bundle.get("5m")
    if df5 is None:
        df5 = df15
    last15 = df15.iloc[-1]
    last5 = df5.iloc[-1]
    price = float(getattr(last5, "close", getattr(last15, "close", 0.0)))
    atr = float(getattr(last15, "atr14", 0.0) or _atr(df15, 14) or 0.0)
    atr = max(atr, abs(price) * 1e-4)
    sup_levels = list(levels.get("support") or [])
    res_levels = list(levels.get("resistance") or [])
    sup1 = float(sup_levels[0]) if sup_levels else price * 0.985
    res1 = float(res_levels[0]) if res_levels else price * 1.015
    sup_psy = _round_number_near(sup1, symbol)
    res_psy = _round_number_near(res1, symbol)
    ema20_15 = float(getattr(last15, "ema20", price))
    vwap15 = float(getattr(last15, "vwap", ema20_15))
    ema20_5 = float(getattr(last5, "ema20", getattr(last5, "ema5", price))) if "ema20" in last5.index else price
    vwap5 = float(getattr(last5, "vwap", ema20_5)) if "vwap" in last5.index else ema20_5
    prev5 = df5.iloc[-2] if len(df5) >= 2 else last5
    delta_m5 = None
    try:
        delta_m5 = float(((fut_signals or {}).get("taker_delta") or {}).get("m5"))
    except Exception:
        delta_m5 = None

    body = abs(float(getattr(last5, "close", price)) - float(getattr(last5, "open", price)))
    range_total = max(float(getattr(last5, "high", price)) - float(getattr(last5, "low", price)), abs(price) * 1e-6)
    bullish = float(getattr(last5, "close", price)) > float(getattr(last5, "open", price))
    bearish = float(getattr(last5, "close", price)) < float(getattr(last5, "open", price))
    body_ratio = body / range_total if range_total > 0 else 0.0
    momentum_m5 = bearish and body_ratio >= 0.55
    momentum_up = bullish and body_ratio >= 0.55

    bo_trigger_long = float(getattr(last5, "high", price)) > res_psy * 1.0002 and float(getattr(last5, "close", price)) > res_psy
    pb_reclaim = (
        float(getattr(last15, "close", price)) > ema20_15
        and float(getattr(last15, "close", price)) > vwap15
        and bullish
        and float(getattr(last5, "close", price)) >= max(ema20_5, vwap5)
    )
    breakdown_micro = float(getattr(last5, "low", price)) < sup_psy * 0.999 and float(getattr(last5, "close", price)) < sup_psy
    reversal_micro = (
        float(getattr(last5, "close", price)) > sup_psy
        and momentum_up
        and float(getattr(last5, "close", price)) >= max(ema20_5, vwap5)
    )
    bo_trigger_short = float(getattr(last5, "low", price)) < sup_psy * 0.9995 and float(getattr(last5, "close", price)) < sup_psy
    pb_retest_fail = (
        float(getattr(prev5, "close", price)) >= sup_psy
        and float(getattr(last5, "close", price)) < sup_psy
        and bearish
        and body_ratio >= 0.4
    )

    swing_long = _micro_swing_price(bundle, "LONG")
    swing_short = _micro_swing_price(bundle, "SHORT")
    sl_long = _apply_sl_buffer(swing_long, "LONG", atr, profile_cfg)
    sl_short = _apply_sl_buffer(swing_short, "SHORT", atr, profile_cfg)

    vol_meta = {}
    vol_curr, vol_ma, vol_tf = _vol_snapshot(bundle, tuple(profile_cfg.get("tf_exec") or ("1m", "5m")))
    if vol_curr is not None:
        vol_meta = {"tf": vol_tf, "current": vol_curr, "ma20": vol_ma, "mult": float(profile_cfg.get("vol_mult", 1.2))}
        vol_meta["ok"] = vol_ok

    cands: List[Dict[str, Any]] = []
    if bias == "LONG":
        if bo_trigger_long and vol_ok:
            entry_break = res_psy + max(0.1 * atr, abs(res_psy) * 1e-5)
            entry_retest = res_psy - max(0.25 * atr, abs(res_psy) * 1e-5)
            entries = [entry_break, entry_retest]
            avg_entry = sum(entries) / len(entries)
            tp1, tp2 = _tp_targets("LONG", avg_entry, atr, profile_cfg)
            sl_val = _resolve_stop(entries, sl_long, atr, price, "LONG")
            cands.append(
                _candidate(
                    "LONG",
                    entries,
                    sl_val,
                    [tp1, tp2],
                    "SCALP_BO_LONG",
                    [
                        "Stop-limit di atas resistance psikologis 15m",
                        "Tambahan di retest range tinggi (reduce-only)",
                    ],
                    vol_ok=True,
                    meta={"volume": vol_meta, "trigger": "breakout", "level": res_psy},
                )
            )
        if pb_reclaim and vol_ok:
            base = min(ema20_15, vwap15)
            entry1 = base
            entry2 = base - max(0.35 * atr, abs(base) * 8e-5)
            entries = [entry1, entry2]
            avg_entry = sum(entries) / len(entries)
            tp1, tp2 = _tp_targets("LONG", avg_entry, atr, profile_cfg)
            sl_val = _resolve_stop(entries, sl_long, atr, price, "LONG")
            cands.append(
                _candidate(
                    "LONG",
                    entries,
                    sl_val,
                    [tp1, tp2],
                    "SCALP_PB_LONG",
                    [
                        "Reclaim EMA20/VWAP 15m + konfirmasi candle M5",
                        "Entry kedua di pullback ringan EMA50/VWAP",
                    ],
                    vol_ok=True,
                    meta={"volume": vol_meta, "trigger": "pullback", "level": base},
                )
            )
        if breakdown_micro and momentum_m5:
            entry_break = sup_psy - max(0.12 * atr, abs(sup_psy) * 1e-5)
            entry_retest = sup_psy
            entries = [entry_break, entry_retest]
            avg_entry = sum(entries) / len(entries)
            tp1, tp2 = _tp_targets("SHORT", avg_entry, atr, profile_cfg)
            delta_note = "" if delta_m5 is None else f"Δ taker m5 {delta_m5:.2f}"
            notes = [
                "Breakdown invalidasi mikro 5m",
                "Momentum bearish M5 jelas (body dominan)",
            ]
            if delta_note:
                notes.append(delta_note)
            sl_val = _resolve_stop(entries, sl_short, atr, price, "SHORT")
            cands.append(
                _candidate(
                    "SHORT",
                    entries,
                    sl_val,
                    [tp1, tp2],
                    "SCALP_BREAK_SHORT",
                    notes,
                    vol_ok=vol_ok,
                    meta={"volume": vol_meta, "trigger": "breakdown", "level": sup_psy},
                )
            )
    else:  # bias SHORT
        if reversal_micro and vol_ok:
            base = max(sup_psy, float(getattr(last5, "low", price)))
            entry1 = base
            entry2 = base - max(0.3 * atr, abs(base) * 7e-5)
            entries = [entry1, entry2]
            avg_entry = sum(entries) / len(entries)
            tp1, tp2 = _tp_targets("LONG", avg_entry, atr, profile_cfg)
            sl_val = _resolve_stop(entries, sl_long, atr, price, "LONG")
            cands.append(
                _candidate(
                    "LONG",
                    entries,
                    sl_val,
                    [tp1, tp2],
                    "SCALP_REV_LONG",
                    [
                        "Reversal mikro di atas support kunci",
                        "Volume konfirmasi & body bullish kuat",
                    ],
                    vol_ok=True,
                    meta={"volume": vol_meta, "trigger": "reversal", "level": base},
                )
            )
        if (bo_trigger_short or pb_retest_fail):
            entry_break = sup_psy - max(0.1 * atr, abs(sup_psy) * 1e-5)
            entry_retest = sup_psy + max(0.2 * atr, abs(sup_psy) * 8e-5)
            entries = [entry_break, entry_retest]
            avg_entry = sum(entries) / len(entries)
            tp1, tp2 = _tp_targets("SHORT", avg_entry, atr, profile_cfg)
            trigger = "breakdown" if bo_trigger_short else "retest_fail"
            sl_val = _resolve_stop(entries, sl_short, atr, price, "SHORT")
            cands.append(
                _candidate(
                    "SHORT",
                    entries,
                    sl_val,
                    [tp1, tp2],
                    "SCALP_CONT_SHORT",
                    [
                        "Kontinuasi short: gagal bertahan di support",
                        "Entry kedua di retest naik (swing failure)",
                    ],
                    vol_ok=vol_ok,
                    meta={"volume": vol_meta, "trigger": trigger, "level": sup_psy},
                )
            )
    return cands


def _make_swing_candidates(bundle: Dict[str, pd.DataFrame],
                           levels: Dict[str, Any],
                           profile_cfg: Dict[str, Any],
                           bias: str,
                           symbol: Optional[str],
                           price_pad_bp: float,
                           fut_signals: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    df15 = bundle.get("15m")
    if df15 is None:
        df15 = next(iter(bundle.values()))
    df1h = bundle.get("1h")
    if df1h is None:
        df1h = df15
    price = float(df15.iloc[-1].close)
    atr15 = float(getattr(df15.iloc[-1], "atr14", 0.0) or _atr(df15, 14) or 0.0)
    atr1h = float(getattr(df1h.iloc[-1], "atr14", atr15) or atr15)
    atr_ref = atr1h if str(profile_cfg.get("tf_context", "1h")).lower() == "1h" else atr15
    supports = list(levels.get("support") or [])
    resistances = list(levels.get("resistance") or [])
    s1 = float(supports[0]) if supports else price * 0.97
    s2 = float(supports[1]) if len(supports) > 1 else s1 - max(atr_ref * 0.8, abs(price) * 0.01)
    r1 = float(resistances[0]) if resistances else price * 1.03
    r2 = float(resistances[1]) if len(resistances) > 1 else r1 + max(atr_ref * 0.8, abs(price) * 0.01)

    swing_long = _swing_low(df1h, lookback=12) or s2
    swing_short = _swing_high(df1h, lookback=12) or r2
    sl_long = float(swing_long) - float(profile_cfg.get("sl_buf_atr", 0.8)) * atr_ref
    sl_short = float(swing_short) + float(profile_cfg.get("sl_buf_atr", 0.8)) * atr_ref

    pad = max(price * price_pad_bp / 1e4, atr_ref * 0.2)
    long_e1 = min(price, s1 + pad)
    long_e2 = min(long_e1 - max(atr_ref * 0.35, abs(price) * 6e-4), s2)
    short_e1 = max(price, r1 - pad)
    short_e2 = max(short_e1 + max(atr_ref * 0.35, abs(price) * 6e-4), r2)

    long_entries = [float(long_e1), float(long_e2)]
    short_entries = [float(short_e1), float(short_e2)]
    long_avg = sum(long_entries) / len(long_entries)
    short_avg = sum(short_entries) / len(short_entries)
    tp1_long, tp2_long = _tp_targets("LONG", long_avg, atr_ref, profile_cfg)
    tp1_short, tp2_short = _tp_targets("SHORT", short_avg, atr_ref, profile_cfg)

    cands: List[Dict[str, Any]] = []
    long_notes = [
        "Pullback ke cluster support utama (EMA/VWAP 1H)",
        "Invalid di luar swing 1H - buffer ATR",
    ]
    short_notes = [
        "Reaksi di resistance mayor 1H",
        "Invalid di atas swing lower-high 1H",
    ]
    cands.append(
        _candidate(
            "LONG",
            long_entries,
            sl_long,
            [tp1_long, tp2_long],
            "SWING_PULLBACK_LONG",
            long_notes,
            vol_ok=True,
            meta={"level": s1, "atr": atr_ref},
        )
    )
    cands.append(
        _candidate(
            "SHORT",
            short_entries,
            sl_short,
            [tp1_short, tp2_short],
            "SWING_REJECT_SHORT",
            short_notes,
            vol_ok=True,
            meta={"level": r1, "atr": atr_ref},
        )
    )

    # Momentum delta tambahan untuk bias
    try:
        delta = float(((fut_signals or {}).get("taker_delta") or {}).get("m15"))
        if delta is not None:
            if delta > 0:
                cands[0].setdefault("notes", []).append(f"Taker delta 15m +{delta:.2f}")
            elif delta < 0:
                cands[1].setdefault("notes", []).append(f"Taker delta 15m {delta:.2f}")
    except Exception:
        pass

    return cands


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
                       fee_bp: float = 5.0,
                       slippage_bp: float = 2.0,
                       use_llm_fixes: bool = False,
                       llm_fix_hook=None,
                       fut_signals: Optional[Dict[str, Any]] = None,
                       symbol: Optional[str] = None,
                       profile: str = "scalp") -> Dict[str, Any]:
    """Bangun rencana Futures (scalp/swing) dengan kandidat dua sisi dan TTL profil."""
    profile_key = str(profile or "scalp").lower()
    cfg_raw = dict(PROFILES.get(profile_key, PROFILES["scalp"]))
    ttl_vals = list(cfg_raw.get("ttl_min") or [120, 120])
    ttl_avg = int(round(sum(ttl_vals) / len(ttl_vals))) if ttl_vals else 120
    tp_pct = [int(round(float(x) * 100.0)) for x in (cfg_raw.get("tp_split") or [0.5, 0.5])]
    if len(tp_pct) < 2:
        tp_pct = (tp_pct + tp_pct[:1])[:2]
    weights = list(cfg_raw.get("entry_weights") or [0.5, 0.5])

    price = float(bundle["15m"]["close"].iloc[-1])
    atr15 = _atr(bundle["15m"], 14)
    atr1h = _atr(bundle.get("1h", bundle["15m"]), 14)
    atr_pct = (atr15 / price) * 100.0 if price else 0.0
    atr_context = atr1h if str(cfg_raw.get("tf_context", "15m")).lower() == "1h" else atr15

    vol_curr, vol_ma, vol_tf = _vol_snapshot(bundle, tuple(cfg_raw.get("tf_exec") or ("1m", "5m")))
    vol_ok = True
    if vol_curr is not None and vol_ma not in (None, 0):
        vol_ok = vol_curr >= float(cfg_raw.get("vol_mult", 1.0)) * float(vol_ma)

    hint = (side_hint or "AUTO").upper()
    if hint in {"LONG", "SHORT"}:
        bias = hint
    else:
        bias = "LONG" if _ema_stack_ok(bundle, "LONG") else "SHORT"
        try:
            if fut_signals:
                td15 = float((fut_signals.get("taker_delta") or {}).get("m15") or 0.0)
                basis_bp = float((fut_signals.get("basis") or {}).get("bp") or 0.0)
                if td15 < -0.05 or basis_bp < -20.0:
                    bias = "SHORT"
                elif td15 > 0.05 and basis_bp > 5.0:
                    bias = "LONG"
        except Exception:
            pass

    levels = make_levels(feat)
    if profile_key == "scalp":
        candidate_list = _make_scalp_candidates(bundle, levels, cfg_raw, bias, symbol, vol_ok, fut_signals)
    else:
        candidate_list = _make_swing_candidates(bundle, levels, cfg_raw, bias, symbol, price_pad_bp, fut_signals)

    rr_target = float(rr_min or cfg_raw.get("min_rr", 1.2 if profile_key == "scalp" else 1.6))
    best = pick_by_rr_confluence(candidate_list, rr_target, fee_bp, slippage_bp)
    if best is None and candidate_list:
        best = max(candidate_list, key=lambda c: c.get("rr", -1e9))
    if best is None:
        fallback = _make_swing_candidates(bundle, levels, cfg_raw, bias, symbol, price_pad_bp, fut_signals)
        best = fallback[0] if bias == "LONG" else fallback[1]
        best.setdefault("notes", []).append("Fallback: gunakan struktur swing dasar karena sinyal mikro kurang lengkap.")

    side_final = (best.get("side") or bias or "LONG").upper()
    entries = [float(x) for x in (best.get("entries") or [])][:2]
    if len(entries) < 2 and entries:
        entries = entries + entries[:1]
    if not entries:
        entries = [price, price]
    invalid_price = float(best.get("invalid") or (entries[0] - atr_context if side_final == "LONG" else entries[0] + atr_context))
    tp_vals = [float(x) for x in (best.get("tp") or [])][:2]
    if len(tp_vals) < 2 and tp_vals:
        tp_vals = tp_vals + tp_vals[:1]
    if not tp_vals:
        tp_vals = list(_tp_targets(side_final, sum(entries) / len(entries), atr_context, cfg_raw))

    avg_entry = sum(entries) / len(entries)
    gap_min = max(0.2 * atr_context, abs(avg_entry) * 1e-5)
    if side_final == "LONG":
        invalid_price = min(invalid_price, min(entries) - gap_min)
    else:
        invalid_price = max(invalid_price, max(entries) + gap_min)

    rr_value = compute_rr_min_futures(side_final, entries, tp_vals[0], invalid_price, fee_bp, slippage_bp)
    if rr_value < rr_target:
        eps = max(abs(avg_entry) * 1e-5, 1e-5)
        total_fee = ((fee_bp or 0.0) + (slippage_bp or 0.0)) * 1e-4 * avg_entry
        if side_final == "LONG":
            reward = tp_vals[0] - avg_entry
            reward_net = reward - total_fee
            if reward_net > 0:
                max_risk = max(reward_net / rr_target - total_fee, eps)
                invalid_price = max(invalid_price, avg_entry - max_risk)
            min_tp1 = avg_entry + total_fee + rr_target * ((avg_entry - invalid_price) + total_fee)
            if tp_vals[0] < min_tp1:
                delta = min_tp1 - tp_vals[0]
                tp_vals[0] = min_tp1
                tp_vals[1] = max(tp_vals[1], min_tp1 + max(0.6 * atr_context, delta))
        else:
            reward = avg_entry - tp_vals[0]
            reward_net = reward - total_fee
            if reward_net > 0:
                max_risk = max(reward_net / rr_target - total_fee, eps)
                invalid_price = min(invalid_price, avg_entry + max_risk)
            min_tp1 = avg_entry - (total_fee + rr_target * ((invalid_price - avg_entry) + total_fee))
            if tp_vals[0] > min_tp1:
                delta = tp_vals[0] - min_tp1
                tp_vals[0] = min_tp1
                tp_vals[1] = min(tp_vals[1], min_tp1 - max(0.6 * atr_context, delta))
        rr_value = compute_rr_min_futures(side_final, entries, tp_vals[0], invalid_price, fee_bp, slippage_bp)
    tp_nodes = [
        {
            "name": "TP1",
            "range": [tp_vals[0], tp_vals[0] + (0.18 * atr_context if side_final == "LONG" else -0.18 * atr_context)],
            "reduce_only_pct": tp_pct[0],
        },
        {
            "name": "TP2",
            "range": [tp_vals[1], tp_vals[1] + (0.28 * atr_context if side_final == "LONG" else -0.28 * atr_context)],
            "reduce_only_pct": tp_pct[1],
        },
    ]

    notes = list(best.get("notes") or [])
    label = cfg_raw.get("label", profile_key.title())
    exec_tf = ", ".join(cfg_raw.get("tf_exec") or []) or "-"
    notes.append(
        f"Profil {label}: TF eksekusi {exec_tf} konteks {cfg_raw.get('tf_context', '15m').upper()} • TTL {ttl_vals[0]}–{ttl_vals[1]} menit."
    )
    if vol_curr is not None and vol_ma is not None and vol_ma not in (0, 0.0):
        ratio = vol_curr / vol_ma if vol_ma else 0.0
        notes.append(
            f"Volume {vol_tf or '1-5m'} {vol_curr:.0f} vs MA20 {vol_ma:.0f} ⇒ {ratio:.2f}× (ambang {cfg_raw.get('vol_mult', 1.0):.2f}×)."
        )
    if profile_key == "scalp":
        notes.append("TP1 tercapai → SL ke BE; TTL habis wajib keluar ≥50% bila momentum hilang.")
        notes.append("Hindari entry ±30 menit event merah dan cek orderbook sebelum trigger.")
    else:
        notes.append("TP1 tercapai → SL ke BE, sisanya mengikuti struktur 1H/4H; TTL habis lakukan reduksi 30%.")

    plan = {
        "side": side_final,
        "entries": entries,
        "weights": weights[: len(entries)] if len(weights) == len(entries) else [0.5, 0.5][: len(entries)],
        "invalids": {"hard_1h": float(invalid_price)},
        "tp": tp_nodes,
        "notes": notes,
        "gates": {"checked": False, "ok": True, "reasons": []},
        "metrics": {
            "rr_min": float(rr_value),
            "rr_target": float(rr_target),
            "atr_pct": float(atr_pct),
            "atr_ctx": float(atr_context),
            "volume_ok": bool(vol_ok),
            "volume_ratio": float(vol_curr / vol_ma) if (vol_curr is not None and vol_ma not in (None, 0)) else None,
        },
        "score": int(round(float(rr_value) * 10.0)),
        "profile": profile_key,
        "profile_config": dict(cfg_raw),
        "ttl_min": ttl_avg,
        "ttl_window": ttl_vals,
        "tp_pct": tp_pct,
        "tf_exec": cfg_raw.get("tf_exec"),
        "tf_context": cfg_raw.get("tf_context"),
        "tf_base": cfg_raw.get("tf_context"),
        "profile_label": label,
        "setup": best.get("setup"),
        "vol_snapshot": {
            "tf": vol_tf,
            "current": vol_curr,
            "ma20": vol_ma,
            "ok": bool(vol_ok),
        },
    }

    try:
        plan = round_futures_prices(symbol or "BTCUSDT", plan)
        from .rounding import precision_for
        prec = precision_for(symbol or "BTCUSDT") or {}
        plan.setdefault("metrics", {})
        if prec.get("tickSize") is not None:
            plan["metrics"]["tick_size"] = float(prec.get("tickSize"))
        if prec.get("stepSize") is not None:
            plan["metrics"]["step_size"] = float(prec.get("stepSize"))
    except Exception:
        pass

    if fut_signals is not None:
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
        gates_ok, reasons, dumps = gating_signals_ok(plan.get("side", side_final), sig2, profile=profile_key)
        plan["gates"] = {"checked": True, "ok": bool(gates_ok), "reasons": reasons, "snapshot": dumps}

    if use_llm_fixes:
        def _default_llm_fix_hook(p0: Dict[str, Any], *, bundle: Dict[str, pd.DataFrame], symbol: Optional[str] = None) -> Dict[str, Any]:
            try:
                import json as _json
                snapshot = {
                    "price": float(bundle["15m"].iloc[-1].close),
                    "atr15": float(bundle["15m"].iloc[-1].atr14),
                    "atr_ctx": plan.get("metrics", {}).get("atr_ctx"),
                    "ema": {
                        "15m": {
                            "ema20": float(getattr(bundle["15m"].iloc[-1], "ema20", 0.0)),
                            "vwap": float(getattr(bundle["15m"].iloc[-1], "vwap", 0.0)),
                        },
                        "1h": {
                            "ema20": float(getattr(bundle.get("1h", bundle["15m"]).iloc[-1], "ema20", 0.0)),
                            "ema50": float(getattr(bundle.get("1h", bundle["15m"]).iloc[-1], "ema50", 0.0)),
                        },
                    },
                }
                payload = {
                    "symbol": symbol or "BTCUSDT",
                    "precision": plan.get("metrics", {}),
                    "fees": {"fee_bp": fee_bp, "slippage_bp": slippage_bp},
                    "profile": {
                        "name": profile_key,
                        "min_rr": rr_target,
                        "sl_buf_atr": cfg_raw.get("sl_buf_atr"),
                        "tp_atr": cfg_raw.get("tp_atr"),
                        "ttl_min": ttl_vals,
                    },
                    "context": {
                        "atr15": snapshot.get("atr15"),
                        "vwap_15m": snapshot["ema"]["15m"]["vwap"],
                        "ema20_15m": snapshot["ema"]["15m"]["ema20"],
                        "ema20_1h": snapshot["ema"]["1h"]["ema20"],
                        "ema50_1h": snapshot["ema"]["1h"]["ema50"],
                        "volume_ma20_1m5m": plan.get("vol_snapshot", {}).get("ma20"),
                    },
                    "draft_plan": {
                        "side": plan.get("side"),
                        "entries": plan.get("entries"),
                        "invalid": plan.get("invalids", {}).get("hard_1h"),
                        "tp": [tp_nodes[0]["range"][0], tp_nodes[1]["range"][0]],
                        "notes": plan.get("notes", [])[:4],
                    },
                }
                user_lines = [
                    "USER INPUT:",
                    _json.dumps(payload, ensure_ascii=False),
                    "SCHEMA JSON:",
                    '{"entries":[{"price":float,"weight":float}],"invalid":float,"tp":[{"name":"TP1","price":float,"qty_pct":int},{"name":"TP2","price":float,"qty_pct":int}],"ttl_min":int}',
                    "CONSTRAINTS:",
                    f"- RR TP1 ≥ {rr_target}; SL = swing_micro ± sl_buf_atr×ATR15m; TP1/TP2 = +tp_atr×ATR15m dari avg_entry",
                    "- qty_pct total = 100; rounding ke tick; invalid < entry (LONG) / invalid > entry (SHORT)",
                    '- Jika volume < threshold → naikkan entry (BO) atau tolak (kembalikan alasan "no_trade_low_volume")',
                ]
                messages = [
                    {
                        "role": "system",
                        "content": "Anda adalah asisten tuning angka untuk rencana FUTURES profil SCALPING. Balas HANYA JSON sesuai schema. Fokus pada efisiensi: TF eksekusi 1–5m, konteks 15m.",
                    },
                    {
                        "role": "user",
                        "content": "\n".join(user_lines),
                    },
                ]
                text_llm, usage = ask_llm_messages(messages)
                from .llm import safe_json_loads
                data = safe_json_loads(text_llm or "") if text_llm else {}
                if not isinstance(data, dict) or not data:
                    return p0
                plan_new = dict(p0)
                plan_new.setdefault("_usage", {})
                if usage:
                    plan_new["_usage"].update({
                        "prompt_tokens": int((usage or {}).get("prompt_tokens") or 0),
                        "completion_tokens": int((usage or {}).get("completion_tokens") or 0),
                        "total_tokens": int((usage or {}).get("total_tokens") or 0),
                    })
                if isinstance(data.get("entries"), list) and data["entries"]:
                    try:
                        prices = [float(node.get("price")) for node in data["entries"][:2] if node.get("price") is not None]
                        if prices:
                            if len(prices) == 1:
                                prices = prices + prices
                            plan_new["entries"] = prices[:2]
                            weights_new = [float(node.get("weight", 0.5)) for node in data["entries"][:2]]
                            if len(weights_new) == len(prices):
                                plan_new["weights"] = weights_new[:2]
                    except Exception:
                        pass
                if data.get("invalid") is not None:
                    try:
                        plan_new.setdefault("invalids", {})["hard_1h"] = float(data["invalid"])
                    except Exception:
                        pass
                if isinstance(data.get("tp"), list) and data["tp"]:
                    tp_new = []
                    for node in data["tp"][:2]:
                        try:
                            price_tp = float(node.get("price"))
                        except Exception:
                            continue
                        tp_new.append({
                            "name": node.get("name") or f"TP{len(tp_new)+1}",
                            "range": [price_tp, price_tp],
                            "reduce_only_pct": int(node.get("qty_pct", 50)),
                        })
                    if tp_new:
                        plan_new["tp"] = tp_new
                if data.get("ttl_min") is not None:
                    plan_new["ttl_min"] = int(data.get("ttl_min"))
                rr_new = compute_rr_min_futures(
                    plan_new.get("side", side_final),
                    plan_new.get("entries", entries),
                    plan_new.get("tp", tp_nodes)[0]["range"][0] if plan_new.get("tp") else tp_vals[0],
                    plan_new.get("invalids", {}).get("hard_1h", invalid_price),
                    fee_bp,
                    slippage_bp,
                )
                plan_new.setdefault("metrics", {})["rr_min"] = float(rr_new)
                return plan_new if rr_new >= rr_target else p0
            except Exception:
                return p0

        try:
            hook = llm_fix_hook if callable(llm_fix_hook) else _default_llm_fix_hook
            plan = hook(plan, bundle=bundle, symbol=symbol)
        except Exception:
            pass

    return plan

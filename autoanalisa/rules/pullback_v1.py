from __future__ import annotations

from typing import List, Optional

from ..schemas.signal_v1 import Signal
from ..utils.num import pct_targets, round_to, position_size


def _atr_pct(payload: dict) -> float:
    try:
        atr = float(payload["tf"]["1H"]["atr14"])
        last = float(payload["tf"]["1H"]["last"])
        return (atr / last) * 100.0 if last else 0.0
    except Exception:
        return 0.0


def _spread_ok(payload: dict) -> bool:
    try:
        spread = float(payload["orderbook"]["spread"]) or 0.0
        last = float(payload["tf"]["15m"]["last"]) or 0.0
        return (spread / last) < (0.05 / 100.0) if last else False
    except Exception:
        return False


def gating_ok(payload: dict) -> bool:
    # trend
    struct = payload.get("structure", {})
    tf1h = payload["tf"]["1H"]
    ema50 = float(tf1h["ema"].get("50", 0))
    ema200 = float(tf1h["ema"].get("200", 0))
    last = float(tf1h["last"])
    is_trend_up = last > ema50 and ema50 > ema200
    is_trend_down = last < ema50 and ema50 < ema200

    # funding (futures only); spot treated as ok
    if payload.get("market") == "futures":
        fr = (payload.get("derivatives") or {}).get("funding_rate")
        if fr is not None and abs(float(fr)) > 0.0002:
            return False

    if not _spread_ok(payload):
        return False

    atr_pct = _atr_pct(payload)
    if not (1.0 <= atr_pct <= 8.0):
        return False

    return True


def _setup_L1(payload: dict) -> Optional[Signal]:
    # Pullback to EMA20 1H ±0.2*ATR1H, reclaim EMA50 15m
    tf1h = payload["tf"]["1H"]
    tf15 = payload["tf"]["15m"]
    ema20_1h = float(tf1h["ema"].get("20", 0))
    atr1h = float(tf1h.get("atr14", 0))
    last15 = float(tf15["last"])
    ema50_15 = float(tf15["ema"].get("50", 0))

    if ema20_1h == 0 or atr1h == 0 or ema50_15 == 0:
        return None
    zone_low = ema20_1h - 0.2 * atr1h
    zone_high = ema20_1h + 0.2 * atr1h

    # require reclaim: last close above EMA50 15m
    if not (zone_low <= last15 <= zone_high and last15 > ema50_15):
        return None

    entry_mid = (zone_low + zone_high) / 2.0
    sl = min(entry_mid - 0.8 * float(payload["tf"]["15m"]["atr14"]), entry_mid * 0.999)  # fallback small gap
    tps = [1.2, 2.2, 3.5]
    tp_price = pct_targets(entry_mid, tps, side="long")

    # sizing
    bal = (payload.get("account") or {}).get("balance_usdt") or 1000.0
    risk_pt = (payload.get("account") or {}).get("risk_per_trade") or 0.01
    risk_usdt = bal * risk_pt
    qty_step = payload.get("precision", {}).get("qty") or 0.1
    qty = position_size(risk_usdt, entry_mid, sl, qty_step=qty_step)

    price_step = payload.get("precision", {}).get("price") or 0.0001
    entry_zone = [round_to(zone_low, price_step), round_to(zone_high, price_step)]
    sl_r = round_to(sl, price_step)
    tp_price_r = [round_to(p, price_step) for p in tp_price]

    return Signal(
        symbol=payload["symbol"],
        market=payload["market"],
        side="long",
        setup="L1_ema20_1h_reclaim_15m",
        score=70,
        entry_zone=entry_zone,
        invalid_level=sl_r,
        sl=sl_r,
        tp=[f"+{x}%" for x in tps],
        tp_price=tp_price_r,
        risk_per_trade=risk_pt,
        position_sizing={"method": "fixed_risk", "qty": qty},
        notes=["reclaim EMA50 15m", "zone EMA20 1H ±0.2*ATR1H"],
        timeframe_confirmations={"confirm_tf": "15m", "support_tf": "1H"},
    )


def _setup_S1(payload: dict) -> Optional[Signal]:
    # Breakdown & retest fail 15m (only for futures; spot long-only will filter later)
    tf15 = payload["tf"]["15m"]
    last15 = float(tf15["last"])
    ema50_15 = float(tf15["ema"].get("50", 0))
    if not (last15 < ema50_15 and ema50_15 > 0):
        return None
    # entry near ema50 + 0.1*ATR15m
    zone_low = ema50_15
    zone_high = ema50_15 + 0.1 * float(tf15.get("atr14", 0))
    entry_mid = (zone_low + zone_high) / 2.0
    sl = entry_mid + 0.8 * float(tf15.get("atr14", 0))
    tps = [1.2, 2.2, 3.5]
    tp_price = pct_targets(entry_mid, tps, side="short")

    bal = (payload.get("account") or {}).get("balance_usdt") or 1000.0
    risk_pt = (payload.get("account") or {}).get("risk_per_trade") or 0.01
    risk_usdt = bal * risk_pt
    qty_step = payload.get("precision", {}).get("qty") or 0.1
    qty = position_size(risk_usdt, entry_mid, sl, qty_step=qty_step)
    price_step = payload.get("precision", {}).get("price") or 0.0001
    entry_zone = [round_to(zone_low, price_step), round_to(zone_high, price_step)]
    sl_r = round_to(sl, price_step)
    tp_price_r = [round_to(p, price_step) for p in tp_price]

    return Signal(
        symbol=payload["symbol"],
        market=payload["market"],
        side="short",
        setup="S1_breakdown_retest_fail_15m",
        score=68,
        entry_zone=entry_zone,
        invalid_level=sl_r,
        sl=sl_r,
        tp=[f"+{x}%" for x in tps],
        tp_price=tp_price_r,
        risk_per_trade=risk_pt,
        position_sizing={"method": "fixed_risk", "qty": qty},
        notes=["below EMA50 15m"],
        timeframe_confirmations={"confirm_tf": "15m"},
    )


def generate_signals(payload: dict) -> List[Signal]:
    if not gating_ok(payload):
        return []

    candidates: list[Signal] = []
    # Spot long-only: skip short setups entirely
    if payload.get("market") == "spot":
        long_sig = _setup_L1(payload)
        if long_sig:
            candidates.append(long_sig)
    else:
        for fn in (_setup_L1, _setup_S1):
            sig = fn(payload)
            if sig:
                candidates.append(sig)

    if not candidates:
        return []
    # select highest score; if conflict long/short and |diff| < 5 → no-trade
    candidates.sort(key=lambda s: s.score, reverse=True)
    best = candidates[0]
    if len(candidates) >= 2:
        other = candidates[1]
        if best.side != other.side and abs(best.score - other.score) < 5:
            return []
    # Threshold
    return [best] if best.score >= 60 else []


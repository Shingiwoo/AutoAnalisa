from __future__ import annotations

from typing import List, Optional

from ..schemas.signal_v1 import Signal
from ..utils.num import pct_targets, round_to, position_size
from ..utils.time import current_session_bias, now_tz


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
    # robust reclaim/retest using series if provided
    c5 = tf15.get("close_last5") or []
    ema50_5 = tf15.get("ema50_last5") or []
    reclaim_ok = last15 > ema50_15
    if c5 and ema50_5 and len(c5) >= 3 and len(ema50_5) >= 3:
        # condition: cross above after being below within last 3 bars
        prev_below = c5[-3] < ema50_5[-3]
        cross_up = c5[-2] >= ema50_5[-2]
        hold_above = c5[-1] > ema50_5[-1]
        reclaim_ok = prev_below and cross_up and hold_above
    if not (zone_low <= last15 <= zone_high and reclaim_ok):
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

    sig = Signal(
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
    # Macro bias scoring tweak
    bias = payload.get("session_bias") or current_session_bias(now_tz())
    btc_bias = payload.get("btc_bias")
    if bias == "bullish":
        sig.score += 10
        sig.notes.append("session bias: bullish")
    elif bias == "bearish":
        sig.score -= 10
        sig.notes.append("session bias: bearish")
    if btc_bias == "bullish":
        sig.score += 10
        sig.notes.append("btc bias: bullish")
    elif btc_bias == "bearish":
        sig.score -= 10
        sig.notes.append("btc bias: bearish")
    return sig


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

    sig = Signal(
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
    bias = payload.get("session_bias") or current_session_bias(now_tz())
    btc_bias = payload.get("btc_bias")
    if bias == "bearish":
        sig.score += 10
        sig.notes.append("session bias: bearish")
    elif bias == "bullish":
        sig.score -= 10
        sig.notes.append("session bias: bullish")
    if btc_bias == "bearish":
        sig.score += 10
        sig.notes.append("btc bias: bearish")
    elif btc_bias == "bullish":
        sig.score -= 10
        sig.notes.append("btc bias: bullish")
    return sig


def _setup_L2(payload: dict) -> Optional[Signal]:
    # Oversold Bounce 5m (Scalp 1–3%): RSI6 5m < 20 and divergence (simplified: RSI6 < 20)
    tf = payload["tf"].get("5m") or payload["tf"].get("15m")
    if not tf:
        return None
    rsi6 = float(tf["rsi"].get("6", 0))
    rsi6_series = tf.get("rsi6_last5") or []
    closes = tf.get("close_last5") or []
    if rsi6 >= 20:
        return None
    # bullish divergence (simple): last price low <= prior low while RSI last > prior RSI low
    div_ok = True
    if rsi6_series and closes and len(rsi6_series) >= 3 and len(closes) >= 3:
        prev_low = min(closes[-3], closes[-2])
        last_low = closes[-1]
        prev_rsi_low = min(rsi6_series[-3], rsi6_series[-2])
        last_rsi = rsi6_series[-1]
        div_ok = (last_low <= prev_low) and (last_rsi > prev_rsi_low)
    if not div_ok:
        return None
    entry = float(tf["last"])
    sl = entry - 0.6 * float(tf.get("atr14", 0))
    tps = [1.0, 2.0, 3.0]
    tp_price = pct_targets(entry, tps, side="long")
    price_step = payload.get("precision", {}).get("price") or 0.0001
    qty_step = payload.get("precision", {}).get("qty") or 0.1
    bal = (payload.get("account") or {}).get("balance_usdt") or 1000.0
    risk_pt = (payload.get("account") or {}).get("risk_per_trade") or 0.01
    qty = position_size(bal * risk_pt, entry, sl, qty_step)
    sig = Signal(
        symbol=payload["symbol"], market=payload["market"], side="long", setup="L2_oversold_bounce_5m",
        score=65, entry_zone=[round_to(entry, price_step), round_to(entry, price_step)], invalid_level=round_to(sl, price_step), sl=round_to(sl, price_step),
        tp=[f"+{x}%" for x in tps], tp_price=[round_to(x, price_step) for x in tp_price], risk_per_trade=risk_pt, position_sizing={"method":"fixed_risk","qty":qty},
        notes=["RSI6 < 20"], timeframe_confirmations={"confirm_tf": "5m" if "5m" in payload.get("tf", {}) else "15m"}
    )
    bias = payload.get("session_bias") or current_session_bias(now_tz())
    btc_bias = payload.get("btc_bias")
    if bias == "bullish":
        sig.score += 10
    elif bias == "bearish":
        sig.score -= 10
    if btc_bias == "bullish":
        sig.score += 10
    elif btc_bias == "bearish":
        sig.score -= 10
    return sig


def _setup_L3(payload: dict) -> Optional[Signal]:
    # Rebreak Range 15m: breakout above range high with retest (simplified)
    tf15 = payload["tf"].get("15m")
    if not tf15:
        return None
    last = float(tf15["last"])
    # Approximate range with support/resistance from payload levels if present
    lv = (payload.get("levels") or {}).get("15m") or {"support": [], "resistance": []}
    if not lv.get("resistance"):
        return None
    hi = max(lv.get("resistance"))
    if last <= hi:
        return None
    atr = float(tf15.get("atr14", 0))
    zone_low = hi
    zone_high = hi + 0.1 * atr
    entry_mid = (zone_low + zone_high) / 2.0
    sl = hi - 0.7 * atr
    # require retest: previous close within 0.1*ATR of hi
    c5 = tf15.get("close_last5") or []
    if c5 and abs(c5[-2] - hi) > 0.1 * atr:
        return None
    tps = [1.5, 2.5, 4.0]
    tp_price = pct_targets(entry_mid, tps, side="long")
    price_step = payload.get("precision", {}).get("price") or 0.0001
    qty_step = payload.get("precision", {}).get("qty") or 0.1
    bal = (payload.get("account") or {}).get("balance_usdt") or 1000.0
    risk_pt = (payload.get("account") or {}).get("risk_per_trade") or 0.01
    qty = position_size(bal * risk_pt, entry_mid, sl, qty_step)
    sig = Signal(
        symbol=payload["symbol"], market=payload["market"], side="long", setup="L3_rebreak_range_15m",
        score=66, entry_zone=[round_to(zone_low, price_step), round_to(zone_high, price_step)], invalid_level=round_to(sl, price_step), sl=round_to(sl, price_step),
        tp=[f"+{x}%" for x in tps], tp_price=[round_to(x, price_step) for x in tp_price], risk_per_trade=risk_pt, position_sizing={"method":"fixed_risk","qty":qty},
        notes=["breakout range 15m"], timeframe_confirmations={"confirm_tf": "15m"}
    )
    bias = payload.get("session_bias") or current_session_bias(now_tz())
    btc_bias = payload.get("btc_bias")
    if bias == "bullish":
        sig.score += 10
    elif bias == "bearish":
        sig.score -= 10
    if btc_bias == "bullish":
        sig.score += 10
    elif btc_bias == "bearish":
        sig.score -= 10
    return sig


def _setup_S2(payload: dict) -> Optional[Signal]:
    # Pop to 1H supply cluster then reject (simplified: near EMA20 1H + above 15m resist then reject)
    tf1h = payload["tf"].get("1H")
    tf15 = payload["tf"].get("15m")
    if not tf1h or not tf15:
        return None
    ema20 = float(tf1h["ema"].get("20", 0))
    last15 = float(tf15["last"])
    atr15 = float(tf15.get("atr14", 0))
    if ema20 == 0 or atr15 == 0:
        return None
    # Price popped above cluster and back below lower bound (reject): simulate by last below ema20 after touching above
    touched = last15 > (ema20 + 0.1 * atr15)
    rejected = last15 < ema20
    if not (touched and rejected):
        return None
    zone_low = ema20
    zone_high = ema20 + 0.1 * atr15
    entry_mid = (zone_low + zone_high) / 2.0
    sl = entry_mid + 0.9 * atr15
    tps = [1.7, 3.0, 4.0]
    tp_price = pct_targets(entry_mid, tps, side="short")
    price_step = payload.get("precision", {}).get("price") or 0.0001
    qty_step = payload.get("precision", {}).get("qty") or 0.1
    bal = (payload.get("account") or {}).get("balance_usdt") or 1000.0
    risk_pt = (payload.get("account") or {}).get("risk_per_trade") or 0.01
    qty = position_size(bal * risk_pt, entry_mid, sl, qty_step)
    sig = Signal(
        symbol=payload["symbol"], market=payload["market"], side="short", setup="S2_supply_reject_1h",
        score=70, entry_zone=[round_to(zone_low, price_step), round_to(zone_high, price_step)], invalid_level=round_to(sl, price_step), sl=round_to(sl, price_step),
        tp=[f"+{x}%" for x in tps], tp_price=[round_to(x, price_step) for x in tp_price], risk_per_trade=risk_pt, position_sizing={"method":"fixed_risk","qty":qty},
        notes=["reject from EMA20 1H cluster"], timeframe_confirmations={"confirm_tf": "15m", "support_tf": "1H"}
    )
    bias = payload.get("session_bias") or current_session_bias(now_tz())
    btc_bias = payload.get("btc_bias")
    if bias == "bearish":
        sig.score += 10
    elif bias == "bullish":
        sig.score -= 10
    if btc_bias == "bearish":
        sig.score += 10
    elif btc_bias == "bullish":
        sig.score -= 10
    return sig


def _setup_S3(payload: dict) -> Optional[Signal]:
    # False Break Round Number (use 0.050 steps): detect last near round and under it
    tf15 = payload["tf"].get("15m")
    if not tf15:
        return None
    last = float(tf15["last"])
    # nearest round (0.05 grid):
    step = 0.05
    rn = round(last / step) * step
    # consider false break if last < rn and within 0.2*ATR of rn
    atr = float(tf15.get("atr14", 0))
    if atr == 0:
        return None
    if not (last < rn and abs(last - rn) <= 0.2 * atr):
        return None
    zone_low = rn
    zone_high = rn + 0.1 * atr
    entry_mid = (zone_low + zone_high) / 2.0
    sl = rn + 0.6 * (float(payload["tf"].get("5m", tf15).get("atr14", 0)))
    tps = [1.5, 2.5, 3.5]
    tp_price = pct_targets(entry_mid, tps, side="short")
    price_step = payload.get("precision", {}).get("price") or 0.0001
    qty_step = payload.get("precision", {}).get("qty") or 0.1
    bal = (payload.get("account") or {}).get("balance_usdt") or 1000.0
    risk_pt = (payload.get("account") or {}).get("risk_per_trade") or 0.01
    qty = position_size(bal * risk_pt, entry_mid, sl, qty_step)
    sig = Signal(
        symbol=payload["symbol"], market=payload["market"], side="short", setup="S3_false_break_round_number",
        score=64, entry_zone=[round_to(zone_low, price_step), round_to(zone_high, price_step)], invalid_level=round_to(sl, price_step), sl=round_to(sl, price_step),
        tp=[f"+{x}%" for x in tps], tp_price=[round_to(x, price_step) for x in tp_price], risk_per_trade=risk_pt, position_sizing={"method":"fixed_risk","qty":qty},
        notes=[f"false break {rn:.3f}"], timeframe_confirmations={"confirm_tf": "15m"}
    )
    bias = payload.get("session_bias") or current_session_bias(now_tz())
    btc_bias = payload.get("btc_bias")
    if bias == "bearish":
        sig.score += 10
    elif bias == "bullish":
        sig.score -= 10
    if btc_bias == "bearish":
        sig.score += 10
    elif btc_bias == "bullish":
        sig.score -= 10
    return sig


def generate_signals(payload: dict) -> List[Signal]:
    if not gating_ok(payload):
        return []

    candidates: list[Signal] = []
    setup_fns = (_setup_L1, _setup_L2, _setup_L3, _setup_S1, _setup_S2, _setup_S3)
    for fn in setup_fns:
        sig = fn(payload)
        if sig:
            # Macro gating: skip conflicting with session bias
            bias = payload.get("session_bias") or current_session_bias(now_tz())
            btc_bias = payload.get("btc_bias")
            if bias == "bearish" and sig.side == "long":
                continue
            if bias == "bullish" and sig.side == "short":
                continue
            if btc_bias == "bearish" and sig.side == "long":
                continue
            if btc_bias == "bullish" and sig.side == "short":
                continue
            # Spot long-only
            if payload.get("market") == "spot" and sig.side == "short":
                continue
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

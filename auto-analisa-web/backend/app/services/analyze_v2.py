from __future__ import annotations

from typing import Dict, Any, Literal

import pandas as pd

from .signal_mtf import calc_symbol_signal
from .indicators import atr
from .market import fetch_klines


async def _safe_last(df: pd.DataFrame, col: str, default: float = 0.0) -> float:
    try:
        if df is None or df.empty:
            return default
        v = float(df[col].iloc[-1])
        return v
    except Exception:
        return default


async def build_quick_analysis(
    symbol: str,
    mode: Literal['fast', 'medium', 'swing'],
    tf_map: Dict[str, str],
    use_context: bool = True,
    market: str = 'futures',
) -> Dict[str, Any]:
    """
    Lightweight Quick Analyze builder that respects the provided tf_map exactly.
    - Uses MTF signal to determine side, total, btc alignment and risk multiplier.
    - Derives simple entries/targets/SL from pattern timeframe via ATR bands.
    """
    # 1) Compute MTF signal strictly with the provided tf_map
    sig = await calc_symbol_signal(
        symbol,
        mode,
        market_type=market,
        context_on=use_context,
        tf_override=tf_map,
    )

    side = (sig.get('signal') or {}).get('side') or 'NO_TRADE'
    total = float(sig.get('total_score_context') if use_context else sig.get('total_score', 0.0))
    risk_mult = float(sig.get('risk_mult', 1.0) or 1.0)
    btc_bias = (sig.get('btc_bias') or {}).get('direction', 'NEUTRAL')
    btc_alignment = 'aligned'
    if side in {'LONG', 'SHORT'} and btc_bias in {'LONG', 'SHORT'} and side != btc_bias:
        btc_alignment = 'conflict'

    # 2) Build simple plan from pattern timeframe
    tf_pat = str(tf_map.get('pattern') or '15m')
    df_pat = await fetch_klines(symbol, tf_pat, limit=240, market=market)
    price_now = await _safe_last(df_pat, 'close', 0.0)
    atr14 = 0.0
    try:
        atr14 = float(atr(df_pat, 14).iloc[-1]) if df_pat is not None and not df_pat.empty else 0.0
    except Exception:
        atr14 = 0.0

    # Fallback ATR
    if not atr14 and price_now:
        atr14 = max(0.001 * price_now, 0.01)

    # Define entries/targets depending on side
    entries, targets, sl = [], [], None
    if price_now > 0 and side in {'LONG', 'SHORT'}:
        k_e1 = 0.25
        k_e2 = 0.50
        k_tp1 = 0.75
        k_tp2 = 1.25
        if side == 'LONG':
            e1 = price_now - k_e1 * atr14
            e2 = price_now - k_e2 * atr14
            tp1 = price_now + k_tp1 * atr14
            tp2 = price_now + k_tp2 * atr14
            sl = price_now - 1.75 * atr14
        else:
            e1 = price_now + k_e1 * atr14
            e2 = price_now + k_e2 * atr14
            tp1 = price_now - k_tp1 * atr14
            tp2 = price_now - k_tp2 * atr14
            sl = price_now + 1.75 * atr14
        entries = [{"label": "E1", "price": round(float(e1), 6)}, {"label": "E2", "price": round(float(e2), 6)}]
        targets = [{"label": "TP1", "price": round(float(tp1), 6)}, {"label": "TP2", "price": round(float(tp2), 6)}]

    return {
        "symbol": symbol.upper(),
        "mode": mode,
        "tf_map": tf_map,
        "btc_alignment": btc_alignment,
        "plan": {
            "entries": entries,
            "take_profits": targets,
            "stop_loss": {"price": round(float(sl), 6)} if sl is not None else None,
        },
        "price": round(float(price_now), 6) if price_now else None,
        "total": round(float(total), 4),
        "risk_mult": round(float(risk_mult), 2),
    }


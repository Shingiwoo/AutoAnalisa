from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Literal, Dict, Any
import time

from ..services.supertrend import compute_supertrend
from ..services.signal_mtf import load_signal_config, _st_cfg_from_preset, _tf_normalize, _load_tf

router = APIRouter(prefix="/api", tags=["ohlcv"])  # include in main.py

_CACHE: Dict[tuple, tuple[float, Dict[str, Any]]] = {}


@router.get("/spark")
async def spark(
    symbol: str,
    tf: str,
    mode: Literal["fast", "medium", "swing"] = Query("fast"),
    kind: Literal["close", "st_line"] = Query("close"),
    limit: int = Query(200, ge=20, le=2000),
):
    """Return sparkline-friendly series with OHLCV + Supertrend components.
    Data indexed by ts ascending order.
    """
    cfg = load_signal_config()
    tf_norm = _tf_normalize(tf)
    # swing safeguard: force pattern TF to 4h if user accidentally passes something else
    # (kept simple: we don't know which panel calls this; UI passes correct tf_map)

    # cache key
    key = (symbol.upper(), tf_norm, mode, kind, int(limit))
    now = time.time()
    ttl = 60.0 if mode == "swing" else 30.0
    if key in _CACHE:
        ts, payload = _CACHE[key]
        if now - ts <= ttl:
            return payload

    df = await _load_tf(symbol, tf_norm, market_type="futures", limit=limit)
    stp = _st_cfg_from_preset(cfg, mode, tf_norm)
    st = compute_supertrend(df, period=stp['period'], multiplier=stp['multiplier'], src=stp['src'], change_atr=stp['change_atr'])
    data = []
    for i, (ts, row) in enumerate(df.iterrows()):
        data.append({
            "ts": ts.isoformat(),
            "close": float(row["close"]),
            "st_line": float(st.supertrend.iloc[i]),
            "st_up": float(st.up.iloc[i]),
            "st_dn": float(st.dn.iloc[i]),
            "trend": int(st.trend.iloc[i]),
            "signal": int(st.signal.iloc[i]),
        })
    out = {"symbol": symbol.upper(), "tf": tf_norm, "mode": mode, "kind": kind, "data": data}
    _CACHE[key] = (now, out)
    return out



from __future__ import annotations
from typing import Dict, Any, Tuple, List


def _spread_ok(spread_abs: float, last_price: float, max_pct: float = 0.0005) -> bool:
    """Ensure absolute spread is within a fraction of last price.
    max_pct default 0.05% (0.0005 fractional).
    """
    try:
        return (float(spread_abs) / max(float(last_price), 1e-9)) < float(max_pct)
    except Exception:
        return False


def _atr_pct_ok(atr_1h: float, last_1h: float, lo: float = 1.0, hi: float = 8.0) -> bool:
    """ATR% sanity for 1H regime: keep within [lo, hi] percent.
    Out-of-range may indicate extreme chop or spike conditions to avoid.
    """
    try:
        pct = (float(atr_1h) / max(float(last_1h), 1e-9)) * 100.0
        return float(lo) <= pct <= float(hi)
    except Exception:
        return False


def _vol_ok(vol_ma10_15m: float, min_usdt: float = 20000.0) -> bool:
    try:
        return float(vol_ma10_15m or 0.0) >= float(min_usdt)
    except Exception:
        return False

# Simple gating from cached futures signals
def gating_signals_ok(side: str, sig: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    rs: List[str] = []
    ok = True
    # Funding bias: avoid extreme positive funding for LONG and extreme negative for SHORT
    try:
        fnow = float((sig.get("funding") or {}).get("now") or 0.0) * 1e4  # to bp
        if side == "LONG" and fnow > 8.0:
            ok = False; rs.append(f"Funding {fnow:.1f}bp terlalu tinggi untuk LONG")
        if side == "SHORT" and fnow < -8.0:
            ok = False; rs.append(f"Funding {fnow:.1f}bp terlalu rendah (negatif) untuk SHORT")
    except Exception:
        pass

    # Long/short ratio extremes → fade
    try:
        lsr_pos = float((sig.get("lsr") or {}).get("positions") or 0.0)
        if side == "LONG" and lsr_pos > 2.2:
            ok = False; rs.append(f"LSR posisi {lsr_pos:.2f} menandakan crowded LONG")
        if side == "SHORT" and lsr_pos < 0.45:
            ok = False; rs.append(f"LSR posisi {lsr_pos:.2f} menandakan crowded SHORT")
    except Exception:
        pass

    # Basis/backwardation
    try:
        basis_bp = float((sig.get("basis") or {}).get("bp") or 0.0)
        if side == "LONG" and basis_bp < -25.0:
            ok = False; rs.append(f"Basis {basis_bp:.1f}bp backwardation dalam → avoid LONG")
        if side == "SHORT" and basis_bp > 40.0:
            ok = False; rs.append(f"Basis {basis_bp:.1f}bp contango kuat → avoid SHORT")
    except Exception:
        pass

    # Taker delta short-term momentum
    try:
        td15 = float((sig.get("taker_delta") or {}).get("m15") or 0.0)
        if side == "LONG" and td15 < -0.08:
            ok = False; rs.append(f"Taker delta 15m {td15:.2f} bearish → hindari LONG")
        if side == "SHORT" and td15 > 0.08:
            ok = False; rs.append(f"Taker delta 15m {td15:.2f} bullish → hindari SHORT")
    except Exception:
        pass

    # Orderbook sanity
    try:
        spread_bp = float((sig.get("orderbook") or {}).get("spread_bp") or 0.0)
        if spread_bp > 6.0:
            ok = False; rs.append(f"Spread {spread_bp:.1f}bp lebar → kondisi tidak ideal")
    except Exception:
        pass

    # Optional: absolute spread and ATR% gating when provided upstream
    try:
        spread_abs = sig.get("spread_abs")
        last_1h = sig.get("last_1h")
        atr_1h = sig.get("atr_1h")
        # If absolute spread is provided with a last price, gate it strictly
        if spread_abs is not None and last_1h is not None:
            if not _spread_ok(float(spread_abs), float(last_1h)):
                ok = False; rs.append("Spread terlalu lebar")
        # If ATR% context available, avoid extreme chop/spike
        if atr_1h is not None and last_1h is not None:
            if not _atr_pct_ok(float(atr_1h), float(last_1h)):
                ok = False; rs.append("ATR% tidak wajar (chop/spike)")
    except Exception:
        pass

    # Optional: volume gating if upstream supplies volume MA in USDT
    try:
        vol_ctx = sig.get("volume") or {}
        # prefer explicit USDT MA for 15m
        ma10 = vol_ctx.get("ma10_15m_usdt") or vol_ctx.get("ma10_15m")
        if ma10 is not None and not _vol_ok(ma10):
            ok = False; rs.append("Volume 15m di bawah ambang")
    except Exception:
        pass

    return ok, rs, {
        "funding": sig.get("funding"),
        "lsr": sig.get("lsr"),
        "basis": sig.get("basis"),
        "taker_delta": sig.get("taker_delta"),
        "orderbook": sig.get("orderbook"),
        "spread_abs": sig.get("spread_abs"),
        "atr_ctx": {"atr_1h": sig.get("atr_1h"), "last_1h": sig.get("last_1h")},
    }

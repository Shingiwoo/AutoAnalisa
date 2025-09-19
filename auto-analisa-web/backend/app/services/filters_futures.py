
from __future__ import annotations
from typing import Dict, Any, Tuple, List

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

    return ok, rs, {
        "funding": sig.get("funding"),
        "lsr": sig.get("lsr"),
        "basis": sig.get("basis"),
        "taker_delta": sig.get("taker_delta"),
        "orderbook": sig.get("orderbook"),
    }

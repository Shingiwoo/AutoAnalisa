from __future__ import annotations
from typing import Optional, Sequence
import os


def _safe_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def calc_rr(entry: float | None, sl: float | None, tp1: float | None, tp2: float | None, tp3: float | None) -> str | None:
    e = _safe_float(entry)
    s = _safe_float(sl)
    tps = list(filter(lambda x: x is not None, [_safe_float(tp1), _safe_float(tp2), _safe_float(tp3)]))
    if e is None or s is None or not tps:
        return None
    risk = abs(e - s)
    if risk <= 0:
        return None
    parts: list[str] = []
    for tp in tps:
        reward = abs(tp - e)
        rr = reward / risk if risk else 0.0
        parts.append(f"1:{rr:.1f}")
    return " | ".join(parts)


def calc_pnl_pct(arah: str | None, entry: float | None, exit: float | None) -> float | None:
    e = _safe_float(entry)
    x = _safe_float(exit)
    if e is None or e == 0 or x is None:
        return None
    direction = (arah or "LONG").upper()
    if direction == "SHORT":
        return (e - x) / e * 100.0
    return (x - e) / e * 100.0


def auto_fields(data: dict) -> dict:
    out: dict = {}
    try:
        saldo_awal = _safe_float(data.get("saldo_awal"))
        margin = _safe_float(data.get("margin"))
        if saldo_awal is not None and margin is not None:
            out["sisa_saldo"] = saldo_awal - margin
    except Exception:
        pass
    try:
        # If TP prices not provided, derive from RR multipliers just for RR string
        e = _safe_float(data.get("entry_price"))
        s = _safe_float(data.get("sl_price"))
        if e is not None and s is not None:
            m = _get_tp_multipliers()
            risk = abs(e - s)
            if risk > 0 and len(m) >= 1:
                parts = [f"1:{float(x):.0f}" if float(x).is_integer() else f"1:{float(x):.1f}" for x in m[:3]]
                out["risk_reward"] = " | ".join(parts)
    except Exception:
        pass
    try:
        pnl = calc_pnl_pct(data.get("arah"), data.get("entry_price"), data.get("exit_price"))
        if pnl is not None:
            out["pnl_pct"] = pnl
    except Exception:
        pass
    return out


def _get_tp_multipliers() -> list[float]:
    raw = os.getenv("JOURNAL_TP_MULTS", "2,3,4")
    vals: list[float] = []
    for part in raw.split(","):
        try:
            vals.append(float(part.strip()))
        except Exception:
            continue
    return vals or [2.0, 3.0, 4.0]


def derive_targets(arah: str, entry: float, sl: float, mults: Sequence[float] | None = None) -> dict:
    """Compute BE and TP prices from entry, SL, and RR multipliers.

    Returns dict: { be_price, tp1_price, tp2_price, tp3_price, risk_reward }
    """
    m = list(mults) if mults else _get_tp_multipliers()
    m = (m + [None, None, None])[:3]  # ensure len>=3 (fill None)
    be = float(entry)
    e = float(entry)
    s = float(sl)
    if arah.upper() == "SHORT":
        risk = s - e
        tps = [e - (risk * float(x)) if x is not None else None for x in m]
    else:
        risk = e - s
        tps = [e + (risk * float(x)) if x is not None else None for x in m]
    # risk_reward string from multipliers
    rr_parts = [f"1:{int(x)}" if x is not None and float(x).is_integer() else (f"1:{x:.1f}" if x is not None else None) for x in m]
    rr_str = " | ".join([p for p in rr_parts if p])
    return {
        "be_price": be,
        "tp1_price": tps[0] if tps[0] is not None else be,
        "tp2_price": tps[1] if tps[1] is not None else be,
        "tp3_price": tps[2] if tps[2] is not None else be,
        "risk_reward": rr_str,
    }


def calc_equity_balance(saldo_awal: float | None, margin: float | None, leverage: float | None, arah: str | None, entry_price: float | None, exit_price: float | None) -> Optional[float]:
    try:
        sa = _safe_float(saldo_awal)
        m = _safe_float(margin)
        lev = _safe_float(leverage)
        e = _safe_float(entry_price)
        x = _safe_float(exit_price)
        if sa is None or m is None or lev is None or e is None or e == 0 or x is None:
            return None
        qty = (m * lev) / e
        if (arah or "LONG").upper() == "SHORT":
            pnl_abs = qty * (e - x)
        else:
            pnl_abs = qty * (x - e)
        return sa + pnl_abs
    except Exception:
        return None

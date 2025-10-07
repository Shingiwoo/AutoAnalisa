from __future__ import annotations
from typing import Optional


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
        out["risk_reward"] = calc_rr(data.get("entry_price"), data.get("sl_price"), data.get("tp1_price"), data.get("tp2_price"), data.get("tp3_price"))
    except Exception:
        pass
    try:
        pnl = calc_pnl_pct(data.get("arah"), data.get("entry_price"), data.get("exit_price"))
        if pnl is not None:
            out["pnl_pct"] = pnl
    except Exception:
        pass
    return out


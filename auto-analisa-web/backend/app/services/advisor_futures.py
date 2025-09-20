from __future__ import annotations
from typing import Dict, Any, List, Optional
from .validator_futures import compute_rr_min_futures


def _first_num(x):
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, (list, tuple)) and x:
        v = x[0] if isinstance(x[0], (int, float)) else None
        return float(v) if v is not None else None
    return None


def _round_to_tick(x: Optional[float], tick: Optional[float]) -> Optional[float]:
    if x is None or tick is None or tick <= 0:
        return x
    return round(round(float(x) / tick) * tick, 8)


def _trend_hint(mtf_summary: Dict[str, Any]) -> str:
    """Return 'up'|'down'|'mixed' dari EMA stack 1H/4H."""
    try:
        h1 = (mtf_summary or {}).get("1h", {}) or {}
        h4 = (mtf_summary or {}).get("4h", {}) or {}
        up = ("EMA5 > EMA20 > EMA50" in (h1.get("tren_momentum") or "")) or ("EMA5 > EMA20 > EMA50" in (h4.get("tren_momentum") or ""))
        down = ("EMA50 > EMA20 > EMA5" in (h1.get("tren_momentum") or "")) or ("EMA50 > EMA20 > EMA5" in (h4.get("tren_momentum") or ""))
        if up and not down:
            return "up"
        if down and not up:
            return "down"
        return "mixed"
    except Exception:
        return "mixed"


def auto_suggest_futures(
    plan: Dict[str, Any],
    futures_signals: Dict[str, Any],
    mtf_summary: Dict[str, Any],
    precision: Dict[str, Any] | None = None,
    rr_min_threshold: float = 1.5,
    funding_thresh_bp: float = 3.0,
) -> Dict[str, Any]:
    """
    Hasil: { verdict, reasons[], fixes{entries[], tp[], invalids{hard_1h:}}, actions[], severity }
    """
    side = (plan.get("side") or "LONG").upper()
    entries = plan.get("entries") or []
    tps = plan.get("tp") or []
    invalids = plan.get("invalids") or {}
    hard_1h = invalids.get("hard_1h") or invalids.get("h1") or plan.get("invalid") or None

    entries_nums: List[float] = []
    for e in entries:
        num = _first_num(e if not isinstance(e, dict) else e.get("range"))
        if num is not None:
            entries_nums.append(num)
    tp_nums: List[float] = []
    for t in tps:
        num = _first_num(t if not isinstance(t, dict) else t.get("range"))
        if num is not None:
            tp_nums.append(num)

    tick = None
    try:
        tick = float((precision or {}).get("tickSize") or 0) or None
    except Exception:
        tick = None

    reasons: List[str] = []
    actions: List[str] = []
    fixes: Dict[str, Any] = {}
    severity = 0

    # (1) Wrong-side vs tren
    trend = _trend_hint(mtf_summary or {})
    if trend == "up" and side == "SHORT":
        reasons.append("Side SHORT berlawanan dengan tren 1H/4H (EMA stack naik).")
        actions.append("Pertimbangkan tutup-paksa (partial 50–100%) dan flip LONG setelah reclaim EMA20 1H bertahan.")
        severity = max(severity, 3)
    if trend == "down" and side == "LONG":
        reasons.append("Side LONG berlawanan dengan tren 1H/4H (EMA stack turun).")
        actions.append("Pertimbangkan cut loss cepat (partial 50–100%) dan tunggu reclaim EMA20 1H untuk LONG kembali.")
        severity = max(severity, 3)

    # (2) Funding conflict
    try:
        f_now = float(((futures_signals or {}).get("funding") or {}).get("now") or 0.0) * 10000.0
        if side == "LONG" and f_now > funding_thresh_bp:
            reasons.append(f"Funding {f_now:.2f}bp condong LONG; biaya tinggi untuk posisi LONG.")
            actions.append("Kurangi ukuran posisi atau pilih entry pullback lebih rendah; hindari mengejar harga saat funding tinggi.")
            severity = max(severity, 2)
        if side == "SHORT" and f_now < -funding_thresh_bp:
            reasons.append(f"Funding {f_now:.2f}bp condong SHORT; biaya tinggi untuk posisi SHORT.")
            actions.append("Kurangi ukuran posisi atau tambah hanya saat momentum melemah kuat.")
            severity = max(severity, 2)
    except Exception:
        pass

    # (3) RR minimal
    rr = None
    try:
        fee_bp = float(((plan.get("risk") or {}).get("fee_bp")) or 5.0)
    except Exception:
        fee_bp = 5.0
    try:
        slippage_bp = float(((plan.get("risk") or {}).get("slippage_bp")) or 5.0)
    except Exception:
        slippage_bp = 5.0
    try:
        e_nums = [float(x) for x in entries_nums if isinstance(x, (int, float))]
        tp1 = next((x for x in tp_nums if isinstance(x, (int, float))), None)
        rr = compute_rr_min_futures(side, e_nums, tp1 if tp1 is not None else 0.0, hard_1h if hard_1h is not None else 0.0, fee_bp, slippage_bp)
    except Exception:
        rr = None

    if rr is not None and rr < rr_min_threshold and hard_1h is not None and entries_nums:
        # Dorong entries 0.4% menjauh dari harga untuk memperbaiki RR
        adj_pct = 0.004
        def adj(v: float) -> float:
            return v * (1.0 - adj_pct) if side == "LONG" else v * (1.0 + adj_pct)
        new_entries = [_round_to_tick(adj(float(x)), tick) for x in entries_nums]
        inv_adj = hard_1h
        try:
            inv_adj = _round_to_tick(adj(float(hard_1h)), tick)
        except Exception:
            pass
        fixes["entries"] = new_entries
        fixes["invalids"] = {"hard_1h": inv_adj}
        reasons.append(f"RR {rr:.2f} < {rr_min_threshold:.2f}; entry & invalid disetel agar RR minimal tercapai.")
        actions.append("Gunakan bobot lebih besar di entry bawah (LONG) / entry atas (SHORT) untuk memperbaiki RR.")
        severity = max(severity, 2)

    verdict = "tweak" if severity >= 2 else ("warning" if severity == 1 else "valid")
    return {"verdict": verdict, "reasons": reasons, "fixes": fixes, "actions": actions, "severity": severity}


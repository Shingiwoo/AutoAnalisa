from __future__ import annotations
from typing import Dict, List, Tuple


def _weighted_avg(values: List[float], weights: List[float]) -> float:
    if not values:
        return 0.0
    if len(weights) != len(values) or sum(weights) == 0:
        weights = [1.0 / len(values) for _ in values]
    return float(sum(v * w for v, w in zip(values, weights)))


def _compute_rr_tp1_avg(entries: List[float], weights: List[float], invalid: float | None, tp1: float | None) -> float:
    if not entries or invalid is None or tp1 is None:
        return 0.0
    avg_entry = _weighted_avg(entries, weights)
    risk = avg_entry - float(invalid)
    reward = float(tp1) - avg_entry
    if risk <= 0:
        return 0.0
    return float(reward / risk)


def _strict_asc(vals: List[float]) -> List[float]:
    if not vals:
        return vals
    out = [float(vals[0])]
    for v in vals[1:]:
        v = float(v)
        if v <= out[-1]:
            v = out[-1] + max(abs(out[-1]) * 1e-6, 1e-6)
        out.append(v)
    return out


def _round_nums(nums: List[float], digits: int = 6) -> List[float]:
    return [round(float(x), digits) for x in nums]


def _safe_div(a: float, b: float) -> float:
    try:
        return float(a) / float(b)
    except Exception:
        return 0.0


def _nearest_above(values: List[float], ref: float) -> float | None:
    try:
        ordered = sorted(float(v) for v in values if v is not None)
    except Exception:
        return None
    for v in ordered:
        if v > ref:
            return float(v)
    return None


def compute_rr_min(entries: List[float], invalid: float, tp1: float) -> float:
    if not entries or invalid is None or tp1 is None:
        return 0.0
    rr_vals: List[float] = []
    for e in entries:
        if e is None:
            continue
        e = float(e)
        inv = float(invalid)
        t1 = float(tp1)
        # guard degenerate cases
        if e <= 0 or (e - inv) <= 0:
            continue
        rr = _safe_div((t1 - e), (e - inv))
        rr_vals.append(rr)
    return float(min(rr_vals)) if rr_vals else 0.0


def normalize_and_validate(
    plan: Dict,
    rr_target: float = 1.6,
    rr_target_tp1: float = 1.5,
    tighten_cap: float = 0.6,
    context: Dict | None = None,
) -> Tuple[Dict, List[str]]:
    """Normalize numeric fields, enforce basic invariants, compute rr_min.

    Returns (sanitized_plan, warnings)
    """
    p = dict(plan or {})
    warns: List[str] = []
    ctx = dict(context or {})

    # Ensure arrays
    support = list(p.get("support") or [])
    resistance = list(p.get("resistance") or [])
    entries = list(p.get("entries") or [])
    tp = list(p.get("tp") or [])
    weights = list(p.get("weights") or [])
    invalid = p.get("invalid")

    # Normalize numbers and lengths
    try:
        invalid = float(invalid) if invalid is not None else None
    except Exception:
        invalid = None

    # Enforce TP strictly ascending
    tp = _strict_asc([float(x) for x in tp if x is not None])
    # Rounding to 6 decimals as generic default
    support = _round_nums([float(x) for x in support if x is not None])
    resistance = _round_nums([float(x) for x in resistance if x is not None])
    entries = _round_nums([float(x) for x in entries if x is not None])
    tp = _round_nums(tp)
    if invalid is not None:
        invalid = round(float(invalid), 6)

    # Entries/weights sanity
    if len(weights) != len(entries):
        if weights:
            warns.append("weights length != entries; rebalanced equally")
        n = max(1, len(entries))
        weights = [1.0 / n for _ in range(n)]
    else:
        # Coerce to float and normalize sum to 1
        try:
            weights = [float(w) for w in weights]
        except Exception:
            n = max(1, len(entries))
            weights = [1.0 / n for _ in range(n)]
        s = sum(weights) or 1.0
        if abs(s - 1.0) > 1e-6:
            weights = [w / s for w in weights]

    # Compute rr_min to TP1
    tp1 = tp[0] if tp else None
    rr_min = compute_rr_min(entries, invalid, tp1) if (invalid is not None and tp1 is not None) else 0.0
    rr_tp1_avg = _compute_rr_tp1_avg(entries, weights, invalid, tp1)
    p["rr_tp1_avg"] = round(float(rr_tp1_avg), 6)
    p["support"] = support
    p["resistance"] = resistance
    p["entries"] = entries
    p["weights"] = weights
    if invalid is not None:
        p["invalid"] = invalid
    p["tp"] = tp
    p["rr_min"] = round(float(rr_min), 6)
    flags = dict(p.get("flags") or {})
    flags["rr_tp1_ok"] = bool(rr_tp1_avg >= float(rr_target_tp1))
    p["flags"] = flags

    # Basic logical check: invalid should be below entries for long bias; if not, warn
    try:
        if entries and invalid is not None and invalid >= min(entries):
            warns.append("invalid not below entry; check levels")
    except Exception:
        pass

    # Auto-adjust: if rr_min < rr_target, tighten invalid slightly toward entries to reach threshold
    try:
        RR_TH = float(rr_target or 1.6)
        if entries and tp and invalid is not None and rr_min < RR_TH:
            min_entry = float(min(entries))
            # For each entry e: need invalid' <= e - (tp1 - e)/RR => invalid' >= e - (tp1 - e)/RR
            # To satisfy all entries, choose the maximum of these candidates but keep it slightly below min_entry
            candidates = []
            for e in entries:
                e = float(e)
                cand = None
                if tp1 is not None and e is not None:
                    cand = e - (tp1 - e) / RR_TH
                if cand is not None:
                    candidates.append(cand)
            cand_invalid = max(candidates)
            # bound invalid to be below min_entry by small epsilon
            eps = max(abs(min_entry) * 1e-5, 1e-5)
            cand_invalid = min(cand_invalid, min_entry - eps)
            # only adjust upward (tighten) if it increases rr
            if cand_invalid > invalid:
                invalid = round(float(cand_invalid), 6)
                rr_min = compute_rr_min(entries, invalid, tp1) if tp1 is not None else 0.0
                p["invalid"] = invalid
                p["rr_min"] = round(float(rr_min), 6)
                warns.append(f"auto-adjusted invalid to meet rr>={RR_TH}")
    except Exception:
        pass

    # Guard tambahan: pastikan RR TP1 memenuhi target minimal
    if entries and tp and invalid is not None and tp1 is not None and rr_tp1_avg < float(rr_target_tp1):
        avg_entry = _weighted_avg(entries, weights)
        risk0 = avg_entry - float(invalid)
        eps = max(abs(avg_entry) * 1e-5, 1e-5)
        if risk0 > 0:
            target_invalid = avg_entry - (tp1 - avg_entry) / float(rr_target_tp1)
            cap_level = avg_entry - risk0 * float(tighten_cap)
            cand_invalid = max(float(invalid), cap_level, target_invalid)
            cand_invalid = min(cand_invalid, avg_entry - eps)
            if cand_invalid > float(invalid):
                invalid = round(float(cand_invalid), 6)
                p["invalid"] = invalid
                rr_min = compute_rr_min(entries, invalid, tp1)
                rr_tp1_avg = _compute_rr_tp1_avg(entries, weights, invalid, tp1)
                p["rr_min"] = round(float(rr_min), 6)
                p["rr_tp1_avg"] = round(float(rr_tp1_avg), 6)
                flags["rr_tp1_ok"] = bool(rr_tp1_avg >= float(rr_target_tp1))
                if flags["rr_tp1_ok"]:
                    warns.append(f"invalid dinaikkan agar RR TP1 ≥ {float(rr_target_tp1):.2f}")
                else:
                    warns.append("invalid sudah diperketat namun RR TP1 masih rendah")

        if rr_tp1_avg < float(rr_target_tp1):
            resistances = list(ctx.get("resistance") or p.get("resistance") or [])
            avg_entry = _weighted_avg(entries, weights)
            candidate = _nearest_above(resistances, avg_entry)
            if candidate is not None and (tp1 is None or candidate > tp1):
                tp[0] = float(candidate)
                tp = _strict_asc(tp)
                tp1 = tp[0]
                p["tp"] = tp
                rr_min = compute_rr_min(entries, invalid, tp1)
                rr_tp1_avg = _compute_rr_tp1_avg(entries, weights, invalid, tp1)
                p["rr_min"] = round(float(rr_min), 6)
                p["rr_tp1_avg"] = round(float(rr_tp1_avg), 6)
                flags["rr_tp1_ok"] = bool(rr_tp1_avg >= float(rr_target_tp1))
                if flags["rr_tp1_ok"]:
                    warns.append("TP1 dinaikkan ke resist minor untuk RR sehat")

        if rr_tp1_avg < float(rr_target_tp1):
            flags["no_trade"] = True
            warns.append(f"RR TP1 {rr_tp1_avg:.2f} < {float(rr_target_tp1):.2f}; tandai no-trade")
        else:
            flags.pop("no_trade", None)
        p["flags"] = flags

    return p, warns


def validate_spot2(spot2: Dict) -> Dict:
    """Validate and lightly fix SPOT II payload.
    Returns { ok: bool, warnings: [], fixes: {spot2} }
    """
    out = {"ok": True, "warnings": [], "fixes": {}}
    try:
        s2 = dict(spot2 or {})
        entries_raw = None
        use_new_schema = False
        if isinstance(s2.get("entries"), list):
            entries_raw = list(s2.get("entries") or [])
            use_new_schema = True
        else:
            rjb = dict(s2.get("rencana_jual_beli") or {})
            entries_raw = list(rjb.get("entries") or [])
        e_prices: List[float] = []
        weights: List[float] = []
        for e in entries_raw:
            price = None
            if "price" in e:
                try:
                    price = float(e.get("price"))
                except Exception:
                    price = None
            elif "range" in e and e.get("range"):
                try:
                    price = float((e.get("range") or [None])[0])
                except Exception:
                    price = None
            if price is None:
                continue
            e_prices.append(price)
            weights.append(float(e.get("weight") or 0.0))
        tp_nodes = list(s2.get("tp") or [])
        tp_prices: List[float] = []
        for t in tp_nodes:
            price = None
            if "price" in t:
                try:
                    price = float(t.get("price"))
                except Exception:
                    price = None
            elif "range" in t and t.get("range"):
                try:
                    price = float((t.get("range") or [None])[0])
                except Exception:
                    price = None
            if price is not None:
                tp_prices.append(price)
        invalid = None
        if s2.get("invalid") is not None:
            invalid = float(s2.get("invalid"))
        elif not use_new_schema:
            try:
                invalid = float((s2.get("rencana_jual_beli") or {}).get("invalid"))
            except Exception:
                invalid = None

        plan_like = {
            "entries": e_prices,
            "weights": weights,
            "tp": tp_prices,
            "invalid": invalid,
            "support": [],
            "resistance": [],
        }
        fixed, warns = normalize_and_validate(plan_like)
        out["warnings"] = warns

        # Update entries/weights/tp ke struktur asli
        if use_new_schema:
            new_entries = []
            for i, e in enumerate(entries_raw):
                if i >= len(fixed["entries"]):
                    continue
                ne = dict(e)
                ne["price"] = float(fixed["entries"][i])
                if i < len(fixed["weights"]):
                    ne["weight"] = float(fixed["weights"][i])
                new_entries.append(ne)
            s2["entries"] = new_entries
            if fixed.get("invalid") is not None:
                s2["invalid"] = float(fixed["invalid"])
            new_tp = []
            for i, t in enumerate(tp_nodes):
                if i >= len(fixed["tp"]):
                    continue
                nt = dict(t)
                nt["price"] = float(fixed["tp"][i])
                new_tp.append(nt)
            s2["tp"] = new_tp
        else:
            rjb = dict(s2.get("rencana_jual_beli") or {})
            entries = list(rjb.get("entries") or [])
            for i, e in enumerate(entries):
                w = fixed["weights"][i] if i < len(fixed["weights"]) else e.get("weight")
                e["weight"] = float(w)
                try:
                    rng = e.get("range") or []
                    if rng and i < len(fixed["entries"]):
                        rng[0] = float(fixed["entries"][i])
                        e["range"] = rng
                except Exception:
                    pass
            if invalid is not None and fixed.get("invalid") is not None and fixed["invalid"] != invalid:
                rjb["invalid"] = fixed["invalid"]
            s2["rencana_jual_beli"] = rjb
            new_tp = []
            for i, t in enumerate(tp_nodes):
                base = fixed["tp"][i] if i < len(fixed["tp"]) else None
                if base is None:
                    continue
                new_tp.append({
                    "name": t.get("name") or f"TP{i+1}",
                    "range": [base, base],
                    **({k: v for k, v in t.items() if k not in {"range", "name"}}),
                })
            s2["tp"] = new_tp

        # Normalisasi qty_pct agar total 100 bila tersedia
        total_qty = sum(float(t.get("qty_pct", 0.0) or 0.0) for t in s2.get("tp", []))
        if total_qty and abs(total_qty - 100.0) > 1e-3:
            for t in s2.get("tp", []):
                try:
                    t["qty_pct"] = round(float(t.get("qty_pct", 0.0)) * 100.0 / total_qty, 2)
                except Exception:
                    continue

        s2.setdefault("metrics", {})
        s2["metrics"]["rr_min"] = fixed.get("rr_min", 0.0)
        if fixed.get("rr_tp1_avg") is not None:
            s2["metrics"]["rr_tp1_avg"] = fixed.get("rr_tp1_avg")
        if fixed.get("flags"):
            s2["flags"] = dict(fixed.get("flags") or {})

        out["fixes"] = s2
    except Exception as e:
        out["ok"] = False
        out["warnings"].append(str(e))
        out["fixes"] = spot2
    return out

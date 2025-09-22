from __future__ import annotations
from typing import Dict, List, Tuple


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


def _weighted_avg(values: List[float], weights: List[float]) -> float:
    if not values:
        return 0.0
    n = len(values)
    if len(weights) != n or sum(weights) == 0:
        weights = [1.0 / n for _ in range(n)]
    return float(sum(v * w for v, w in zip(values, weights)))


def _fees_adj(bp: float, price: float) -> float:
    # basis points to absolute adjustment on price
    try:
        return float(bp) * 1e-4 * float(price)
    except Exception:
        return 0.0


def compute_rr_min_futures(side: str, entries: List[float], tp1: float, invalid_final: float, fee_bp: float, slippage_bp: float) -> float:
    if not entries or tp1 is None or invalid_final is None:
        return 0.0
    e_avg = _weighted_avg(entries, [1.0 / len(entries)] * len(entries))
    fee_adj = _fees_adj((fee_bp or 0.0) + (slippage_bp or 0.0), e_avg)
    if str(side or "LONG").upper() == "SHORT":
        # Profit when price falls; risk is distance to invalid above
        num = (e_avg - tp1) - fee_adj
        den = (invalid_final - e_avg) + fee_adj
    else:
        num = (tp1 - e_avg) - fee_adj
        den = (e_avg - invalid_final) + fee_adj
    if den <= 0:
        return 0.0
    return float(num / den)


def validate_futures(plan: Dict) -> Dict:
    """Validasi & koreksi ringan FUTURES JSON.
    Mengembalikan { ok, warnings, fixes }
    """
    out = {"ok": True, "warnings": [], "fixes": {}}
    try:
        s = dict(plan or {})
        side = (s.get("side") or "LONG").upper()
        profile = str((s.get("profile") or "scalp")).lower()
        rjb = list(s.get("entries") or [])
        entries: List[float] = []
        weights: List[float] = []
        for i, e in enumerate(rjb):
            rng = list((e.get("range") or []))
            price = float(rng[0]) if rng else None
            if price is None:
                continue
            entries.append(price)
            weights.append(float(e.get("weight") or 0.0))
        tp_nodes = list(s.get("tp") or [])
        tp_prices: List[float] = []
        for t in tp_nodes:
            rng = t.get("range") or []
            if rng:
                tp_prices.append(float(rng[0]))
        invs = dict(s.get("invalids") or {})
        inv_m5 = invs.get("tactical_5m")
        inv_m15 = invs.get("soft_15m")
        inv_h1 = invs.get("hard_1h")
        invalid_final = None
        # pick tiered invalid as final
        try:
            if side == "SHORT":
                # invalid above for short => choose min of available (closest above)
                candidates = [x for x in [inv_m5, inv_m15, inv_h1] if x is not None]
                invalid_final = min(candidates) if candidates else None
            else:
                # long => invalid below => choose max of available (closest below)
                candidates = [x for x in [inv_m5, inv_m15, inv_h1] if x is not None]
                invalid_final = max(candidates) if candidates else None
        except Exception:
            invalid_final = inv_h1 or inv_m15 or inv_m5

        risk = dict(s.get("risk") or {})
        fee_bp = float(risk.get("fee_bp", 0.0) or 0.0)
        slippage_bp = float(risk.get("slippage_bp", 0.0) or 0.0)
        liq_price_est = risk.get("liq_price_est")
        liq_buffer_abs = risk.get("liq_buffer_abs")  # numeric absolute buffer (e.g., k*ATR15m)
        metrics = dict(s.get("metrics") or {})
        rr_req = float(metrics.get("rr_target") or (1.2 if profile == "scalp" else 1.6))
        tp1 = tp_prices[0] if tp_prices else None

        # ensure weights sum=1 and in-range
        if len(weights) != len(entries) or sum(weights) <= 0:
            weights = [1.0 / max(1, len(entries)) for _ in range(len(entries))]
            out["ok"] = False
            out["warnings"].append("weights invalid; normalized equally")
        else:
            ssum = float(sum(weights)) or 1.0
            weights = [float(w) / ssum for w in weights]

        # ensure TP ascending strictly
        tpf = _strict_asc(tp_prices)
        if tpf != tp_prices:
            # rewrite tp nodes
            new_tp = []
            for i, t in enumerate(tp_nodes):
                base = tpf[i] if i < len(tpf) else None
                if base is None:
                    continue
                new_tp.append({"name": t.get("name") or f"TP{i+1}", "range": [base, base], **({k:v for k,v in t.items() if k not in {"range","name"}})})
            s["tp"] = new_tp
            tp_prices = tpf

        # reduce_only sum=100
        try:
            rsum = sum(float(t.get("reduce_only_pct") or 0.0) for t in (s.get("tp") or []))
            if abs(rsum - 100.0) > 1e-6 and s.get("tp"):
                # normalize
                tp_nodes = list(s.get("tp") or [])
                n = len(tp_nodes)
                share = 100.0 / n if n else 0.0
                for t in tp_nodes:
                    t["reduce_only_pct"] = share
                s["tp"] = tp_nodes
        except Exception:
            pass

        # Liq buffer guard: invalid_final must be away from liq by buffer
        try:
            if liq_price_est is not None and liq_buffer_abs is not None and entries:
                e_avg = _weighted_avg(entries, weights)
                if side == "SHORT":
                    # invalid above price; keep it below liq by buffer
                    target_max = float(liq_price_est) - float(liq_buffer_abs)
                    if invalid_final is None or invalid_final > target_max:
                        invalid_final = target_max
                else:
                    # long: invalid below price; keep it above liq by buffer
                    target_min = float(liq_price_est) + float(liq_buffer_abs)
                    if invalid_final is None or invalid_final < target_min:
                        invalid_final = target_min
        except Exception:
            pass

        # RR check >= 1.5 (post fees)
        if entries and tp_prices and invalid_final is not None:
            rr = compute_rr_min_futures(side, entries, tp_prices[0], float(invalid_final), fee_bp, slippage_bp)
            if rr < rr_req:
                # tighten invalid toward entries to meet rr
                e_avg = _weighted_avg(entries, weights)
                eps = max(abs(e_avg) * 1e-5, 1e-5)
                if side == "SHORT":
                    # move invalid upward closer to e_avg
                    target = e_avg + (e_avg - tp_prices[0]) / rr_req
                    invalid_final = max(invalid_final, target + eps)
                else:
                    # move invalid downward closer to e_avg
                    target = e_avg - (tp_prices[0] - e_avg) / rr_req
                    invalid_final = min(invalid_final, target - eps)
                # re-check
                rr2 = compute_rr_min_futures(side, entries, tp_prices[0], float(invalid_final), fee_bp, slippage_bp)
                out["warnings"].append("auto-adjusted invalid_final to meet rr>=1.5")

        # write back invalid_final into invalids hard_1h as canonical for overlay
        if invalid_final is not None:
            invs["hard_1h"] = float(invalid_final)
            s["invalids"] = invs

        out["fixes"] = s
    except Exception as e:
        out["ok"] = False
        out["warnings"].append(str(e))
        out["fixes"] = plan
    return out

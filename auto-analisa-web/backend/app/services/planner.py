from .rules import make_levels, Features
from .fvg import detect_fvg
from .supply_demand import detect_zones
from .budget import get_or_init_settings
from .validator import normalize_and_validate


async def build_plan_async(db, bundle, feat: "Features", score: int, mode: str = "auto"):
    lv = make_levels(feat)
    s1, s2 = lv["support"]
    r1, r2 = lv["resistance"]
    price = float(bundle["15m"].iloc[-1].close)
    # ATR-aware spacing for PB mode
    try:
        atr15 = float(bundle["15m"].iloc[-1].atr14)
    except Exception:
        atr15 = 0.0
    # default spacing factors when ATR available
    if atr15 and atr15 > 0:
        pb1 = max(s1, round(price - 0.5 * atr15, 6))
        pb2 = max(s2, round(price - 1.0 * atr15, 6))
    else:
        pb1, pb2 = max(s1, price * 0.995), max(s2, price * 0.99)
    invalid = min(s2, pb2 * 0.995)
    tp1, tp2 = r1, r2
    if mode == "BO" or (mode == "auto" and price > r1 * 0.995):
        trig = round(r1 * 1.001, 6)
        entries = [trig]
        weights = [1.0]
        out_mode = "BO"
    else:
        entries = [round(pb1, 6), round(pb2, 6)]
        weights = [0.6, 0.4]
        out_mode = "PB"
    bias = "Bullish intraday selama struktur 1H bertahan di atas %.4f–%.4f." % (s1, s2)
    plan = {
        "bias": bias,
        "support": [s1, s2],
        "resistance": [r1, r2],
        "mode": out_mode,
        "entries": entries,
        "weights": weights,
        "invalid": round(invalid, 6),
        "tp": [round(tp1, 6), round(tp2, 6)],
        "score": score,
    }
    # Normalize and compute rr_min
    plan, _warns = normalize_and_validate(plan)
    # Optional overlays (behind feature flags)
    try:
        s = await get_or_init_settings(db)
        if getattr(s, "enable_fvg", False):
            fvg_tf = str(getattr(s, "fvg_tf", "15m"))
            df_fvg = bundle.get(fvg_tf) or bundle.get("15m") or list(bundle.values())[0]
            plan["fvg"] = detect_fvg(
                df_fvg,
                use_bodies=bool(getattr(s, "fvg_use_bodies", False)),
                fill_rule=str(getattr(s, "fvg_fill_rule", "any_touch")),
                threshold_pct=float(getattr(s, "fvg_threshold_pct", 0.0) or 0.0),
                threshold_auto=bool(getattr(s, "fvg_threshold_auto", False)),
            )[:10]
        if getattr(s, "enable_supply_demand", False):
            df_sd = bundle.get("1h") or bundle.get("15m") or list(bundle.values())[0]
            plan["sd_zones"] = detect_zones(
                df_sd,
                max_base=int(getattr(s, "sd_max_base", 3) or 3),
                body_ratio=float(getattr(s, "sd_body_ratio", 0.33) or 0.33),
                min_departure=float(getattr(s, "sd_min_departure", 1.5) or 1.5),
                mode=str(getattr(s, "sd_mode", "swing")),
                vol_div=int(getattr(s, "sd_vol_div", 20) or 20),
                vol_threshold_pct=float(getattr(s, "sd_vol_threshold_pct", 10.0) or 10.0),
            )[:10]
    except Exception:
        pass
    return plan

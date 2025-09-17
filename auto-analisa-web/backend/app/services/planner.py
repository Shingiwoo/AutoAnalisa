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
        # use default weight profile from settings if available
        try:
            from .budget import get_or_init_settings
            import asyncio
            # This function is sync; weights will be finalized later in build_spot2_from_plan
            # Keep a reasonable default DCA (0.4/0.6)
            weights = [0.4, 0.6]
        except Exception:
            weights = [0.4, 0.6]
        out_mode = "PB"
    bias = "Bullish intraday selama struktur 1H bertahan di atas %.4f–%.4f." % (s1, s2)
    # Baseline plan
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

    # Derive invalid bertingkat (tactical 5m, soft 15m, hard 1h, struct 4h[opsional])
    try:
        hard_1h = float(plan.get("invalid")) if plan.get("invalid") is not None else None
        # Soft 15m: sedikit lebih longgar di atas hard_1h (buffer kecil berbasis ATR15m)
        try:
            atr15 = float(bundle["15m"].iloc[-1].atr14)
        except Exception:
            atr15 = 0.0
        buf = max(atr15 * 0.1, abs(hard_1h) * 1e-4) if hard_1h is not None else None
        soft_15m = (hard_1h + (buf or 0.0)) if hard_1h is not None else None
        # Tactical 5m: buffer lebih kecil dari soft
        tac_5m = (hard_1h + (buf or 0.0) * 0.5) if hard_1h is not None else None
        # Struct 4h (opsional): gunakan support struktur lebih dalam (s2) sebagai acuan konservatif
        struct_4h = float(s2) if s2 is not None else None
        plan["invalid_tactical_5m"] = round(float(tac_5m), 6) if tac_5m is not None else None
        plan["invalid_soft_15m"] = round(float(soft_15m), 6) if soft_15m is not None else None
        plan["invalid_hard_1h"] = round(float(hard_1h), 6) if hard_1h is not None else None
        plan["invalid_struct_4h"] = round(float(struct_4h), 6) if struct_4h is not None else None
    except Exception:
        pass
    # MTF summary for UI tabs
    try:
        plan["mtf_summary"] = build_mtf_summary(bundle, feat)
    except Exception:
        pass

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


def _weights_for_profile(profile: str, n: int) -> list[float]:
    if n <= 0:
        return []
    p = (profile or "DCA").upper()
    if n == 1:
        return [1.0]
    if p == "NEAR-PRICE":
        return [0.6, 0.4][:n]
    if p == "BALANCED":
        return [1.0 / n for _ in range(n)]
    # default DCA
    return [0.4, 0.6][:n]


async def build_spot2_from_plan(db, symbol: str, plan: dict) -> dict:
    from .budget import get_or_init_settings
    s = await get_or_init_settings(db)
    profile = getattr(s, "default_weight_profile", "DCA")
    entries = plan.get("entries", [])
    weights = plan.get("weights") or _weights_for_profile(profile, len(entries))
    tp_arr = plan.get("tp", [])
    # helper: safe float
    def _f(x):
        try:
            return float(x)
        except Exception:
            return None
    spot2 = {
        "symbol": symbol,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "ringkas_teknis": plan.get("bias") or "",
        "rencana_jual_beli": {
            "profile": profile,
            "entries": [
                {"range": [float(e), float(e)], "weight": float(weights[i] if i < len(weights) else 0.0), "type": plan.get("mode", "PB")}
                for i, e in enumerate(entries)
            ],
            "invalid": plan.get("invalid"),
            "eksekusi_hanya_jika": "Struktur 1H bertahan sesuai bias."
        },
        "tp": [
            {"name": f"TP{i+1}", "range": [float(t), float(t)]}
            for i, t in enumerate(tp_arr)
        ],
        "mode_breakout": {"trigger": [], "retest_add": [], "sl_cepat": None},
        "fail_safe": [],
        "jam_pantau_wib": [],
        "metrics": {"rr_min": plan.get("rr_min", 0.0), "tick_check": True},
        "sr": {"support": plan.get("support", []), "resistance": plan.get("resistance", [])},
        "invalids": {
            "m5": _f(plan.get("invalid_tactical_5m")),
            "m15": _f(plan.get("invalid_soft_15m")),
            "h1": _f(plan.get("invalid_hard_1h")),
            "h4": _f(plan.get("invalid_struct_4h")),
        },
        "mtf_refs": {},
        "overlays": {"applied": False, "ghost": False},
    }
    return spot2


def _slope(v1: float, v0: float) -> str:
    try:
        dv = float(v1) - float(v0)
        if dv > 0:
            return "+"
        if dv < 0:
            return "-"
        return "0"
    except Exception:
        return "?"


def _fmt_pct(x: float) -> str:
    try:
        return f"{float(x)*100:.2f}%"
    except Exception:
        return "-"


def build_mtf_summary(bundle, feat: "Features") -> dict:
    """Bangun ringkasan MTF ringkas untuk UI (non-JSON di FE)."""
    out: dict = {"trend_utama": ""}
    for tf in ["5m", "15m", "1h", "4h"]:
        if tf not in bundle:
            continue
        df = bundle[tf]
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        # metrics
        close = float(getattr(last, "close", 0.0))
        ema5 = float(getattr(last, "ema5", 0.0)) if "ema5" in df.columns else float("nan")
        ema20 = float(getattr(last, "ema20", 0.0)) if "ema20" in df.columns else float("nan")
        ema50 = float(getattr(last, "ema50", 0.0)) if "ema50" in df.columns else float("nan")
        ema100 = float(getattr(last, "ema100", 0.0)) if "ema100" in df.columns else float("nan")
        ema200 = float(getattr(last, "ema200", 0.0)) if "ema200" in df.columns else float("nan")
        rsi = float(getattr(last, "rsi14", 0.0)) if "rsi14" in df.columns else float("nan")
        rsi_prev = float(getattr(prev, "rsi14", rsi)) if "rsi14" in df.columns else rsi
        macd_hist = float(getattr(last, "hist", 0.0)) if "hist" in df.columns else float("nan")
        macd_hist_prev = float(getattr(prev, "hist", macd_hist)) if "hist" in df.columns else macd_hist
        mb = float(getattr(last, "mb", 0.0)) if "mb" in df.columns else float("nan")
        ub = float(getattr(last, "ub", 0.0)) if "ub" in df.columns else float("nan")
        dn = float(getattr(last, "dn", 0.0)) if "dn" in df.columns else float("nan")
        bw = (ub - dn) / mb if mb else 0.0
        atr14 = float(getattr(last, "atr14", 0.0)) if "atr14" in df.columns else 0.0
        atr_pct = (atr14 / close) if close else 0.0

        # Compose lines
        ema_stack = " > ".join([s for s, cond in [
            ("EMA5", ema5 and ema20 and ema5 > ema20),
            ("EMA20", ema20 and ema50 and ema20 > ema50),
            ("EMA50", ema50 and ema100 and ema50 > ema100),
            ("EMA100", ema100 and ema200 and ema100 > ema200),
            ("EMA200", True),
        ] if s])
        rsi_line = f"RSI {rsi:.1f} ({_slope(rsi, rsi_prev)})"
        macd_line = f"MACD hist {macd_hist:.3f} ({_slope(macd_hist, macd_hist_prev)})"
        bb_line = f"BB bw {_fmt_pct(bw)}"
        atr_line = f"ATR14 {_fmt_pct(atr_pct)}"

        out[tf.replace("m", "m").replace("h", "h")] = {
            "tren_momentum": f"{ema_stack}; {rsi_line}; {macd_line}; {bb_line}; {atr_line}",
            "level_zona": "",
            "skenario": "",
            "catatan": "",
        }
    # trend utama sederhana dari H1/H4
    try:
        h1 = out.get("1h", {})
        h4 = out.get("4h", {})
        out["trend_utama"] = ("Bias utama: " + (h1.get("tren_momentum") or "") + " | " + (h4.get("tren_momentum") or "")).strip()
    except Exception:
        out["trend_utama"] = ""
    return out

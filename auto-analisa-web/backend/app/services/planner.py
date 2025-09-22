from .rules import make_levels, Features
from .regime import detect_regime
from .strategies_spot import assemble
from .fvg import detect_fvg
from .supply_demand import detect_zones
from .budget import get_or_init_settings
from .validator import normalize_and_validate, validate_spot2
from .rounding import round_plan_prices
import math


async def build_plan_async(db, bundle, feat: "Features", score: int, mode: str = "auto"):
    lv = make_levels(feat)
    reg = detect_regime(bundle)
    # Use new regime-aware assembly for SPOT baseline plan
    assembled = assemble(bundle, lv, reg.get("regime", "TREND"))
    plan = {
        **assembled,
        "score": score,
        "regime": reg,
        "swing_highs": lv.get("swing_highs", []),
        "swing_lows": lv.get("swing_lows", []),
    }
    # Normalize and compute rr_min
    # Enforce rr_min target ≥ 1.6 when normalizing
    plan, _warns = normalize_and_validate(plan, rr_target=1.6)
    # sinkronkan tp_logic dengan angka hasil normalisasi
    tp_logic = list(assembled.get("tp_logic") or [])
    tp_vals = list(plan.get("tp") or [])
    if tp_vals and tp_logic:
        while len(tp_logic) < len(tp_vals):
            tp_logic.append(tp_logic[-1])
        plan["tp_logic"] = tp_logic[: len(tp_vals)]
    else:
        plan["tp_logic"] = tp_logic
    plan["entry_notes"] = list(assembled.get("entry_notes") or [])

    # Derive invalid bertingkat (tactical 5m, soft 15m, hard 1h, struct 4h[opsional])
    try:
        hard_1h = float(plan.get("invalid", 0.0)) if plan.get("invalid") is not None else None
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
        s2 = None  # Define s2 or replace with appropriate logic
        struct_4h = float(s2) if s2 is not None else None
        plan["invalid_tactical_5m"] = round(float(tac_5m), 6) if tac_5m is not None else None
        plan["invalid_soft_15m"] = round(float(soft_15m), 6) if soft_15m is not None else None
        plan["invalid_hard_1h"] = round(float(hard_1h), 6) if hard_1h is not None else None
        plan["invalid_struct_4h"] = round(float(struct_4h), 6) if struct_4h is not None else None
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
    # MTF summary for UI tabs (setelah overlay supaya bisa dirujuk)
    try:
        plan["mtf_summary"] = build_mtf_summary(bundle, feat, plan)
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


def _round_numbers(price: float) -> list[float]:
    try:
        p = float(price)
    except Exception:
        return []
    if p <= 0:
        return []
    if p >= 1000:
        step = 10.0
    elif p >= 100:
        step = 5.0
    elif p >= 10:
        step = 1.0
    elif p >= 1:
        step = 0.1
    elif p >= 0.1:
        step = 0.01
    else:
        step = 0.001
    base = math.floor(p / step)
    return [round((base + i) * step, 6) for i in range(1, 4)]


def _build_buyback(plan: dict, bundle, atr15: float) -> list[dict]:
    sup = list(plan.get("support") or [])
    out: list[dict] = []
    atr = float(atr15 or 0.0)
    buf1 = atr * 0.25
    buf2 = atr * 0.35
    buf3 = atr * 0.45
    ema50 = None
    ema100 = None
    try:
        ema50 = float(bundle["15m"].iloc[-1].ema50)
        ema100 = float(bundle["15m"].iloc[-1].ema100)
    except Exception:
        pass
    if sup:
        s1 = float(sup[0])
        out.append({
            "name": "BB1",
            "range": [round(s1 - buf1, 6), round(s1 + buf1, 6)],
            "note": "Support terdekat",
        })
    if len(sup) > 1 or ema50:
        base = float(sup[1]) if len(sup) > 1 else float(ema50 or sup[0])
        out.append({
            "name": "BB2",
            "range": [round(base - buf2, 6), round(base + buf2, 6)],
            "note": "EMA50 / entry lebih aman",
        })
    base3 = None
    if len(sup) > 2:
        base3 = float(sup[2])
    elif ema100:
        base3 = float(ema100)
    if base3 is not None:
        out.append({
            "name": "BB3",
            "range": [round(base3 - buf3, 6), round(base3 + buf3, 6)],
            "note": "EMA100 / support kuat",
        })
    return out[:3]


def _macro_gate() -> dict:
    return {
        "avoid_red": True,
        "prefer_wib": ["11:30-16:00", "19:30-22:00", "00:00-07:00"],
        "avoid_wib": ["16:00-20:45", "22:00-00:00"],
        "session_refs": "Hijau 20:30–23:00 WIB & 01:00–08:00 WITA",
        "sop_partial_on_red": True,
    }


def _macro_notes() -> list[str]:
    return [
        "Checklist: tarik High/Low harian, VWAP, swing 1H, S/D 4H.",
        "Entry PB valid bila 15m close > VWAP saat jendela hijau (20:30–23:00 WIB).",
        "Hindari entry baru di 22:00–01:00 WIB; jika posisi aktif → partial 25-50%.",
        "Pantau DXY & US10Y: risk-on jika melemah; periksa aliran ETF spot BTC & operasi PBOC.",
    ]


def _macro_score(plan: dict, regime: dict) -> tuple[float, float, str]:
    rr = float(plan.get("rr_min") or 0.0)
    score = float(plan.get("score") or 0.0)
    macro_bias = "sideways-bullish"
    total = 0.0
    if regime.get("regime") == "TREND":
        total += 1.0
    if rr >= 1.8:
        total += 1.0
    if score >= 32:
        total += 1.0
    if plan.get("mode") in {"PB", "BO"}:
        total += 0.5
    threshold = 2.0
    return total, threshold, macro_bias


async def build_spot2_from_plan(db, symbol: str, plan: dict, bundle=None) -> dict:
    from .budget import get_or_init_settings

    s = await get_or_init_settings(db)
    # Snap all prices to tick size when possible sebelum membentuk SPOT II+
    try:
        plan = round_plan_prices(symbol, plan)
    except Exception:
        pass
    profile = getattr(s, "default_weight_profile", "DCA")
    entries = list(plan.get("entries", []))
    weights = list(plan.get("weights") or _weights_for_profile(profile, len(entries)))
    tp_arr = list(plan.get("tp", []))
    tp_logic = list(plan.get("tp_logic") or [])
    entry_notes = list(plan.get("entry_notes") or [])
    regime = dict(plan.get("regime") or {})
    mode = plan.get("mode") or "PB"
    bias = plan.get("bias") or ""

    def _f(x):
        try:
            return float(x)
        except Exception:
            return None

    atr15 = None
    try:
        if bundle and "15m" in bundle:
            atr15 = float(bundle["15m"].iloc[-1].atr14)
    except Exception:
        atr15 = None

    entries_struct = []
    for i, price in enumerate(entries):
        val = _f(price)
        if val is None:
            continue
        entry = {
            "price": val,
            "weight": float(weights[i] if i < len(weights) else 0.0),
            "type": mode,
        }
        if i < len(entry_notes) and entry_notes[i]:
            entry["note"] = entry_notes[i]
        entries_struct.append(entry)

    qty_template = [30, 40, 30]
    tp_struct = []
    for i, price in enumerate(tp_arr):
        val = _f(price)
        if val is None:
            continue
        node = {
            "name": f"TP{i+1}",
            "price": val,
            "qty_pct": qty_template[i] if i < len(qty_template) else round(100.0 / max(len(tp_arr), 1), 2),
        }
        if i < len(tp_logic) and tp_logic[i]:
            node["logic"] = tp_logic[i]
        else:
            node["logic"] = ""
        tp_struct.append(node)

    invalid_val = _f(plan.get("invalid"))
    macro_score, macro_threshold, macro_bias = _macro_score(plan, regime)
    buyback = _build_buyback(plan, bundle, atr15)

    spot2 = {
        "symbol": symbol,
        "trade_type": "spot",
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "regime": {
            "regime": regime.get("regime", "TREND"),
            "confidence": float(regime.get("confidence", 0.0) or 0.0),
        },
        "mode": mode,
        "bias": bias,
        "sr": {
            "support": list(plan.get("support", [])),
            "resistance": list(plan.get("resistance", [])),
        },
        "entries": entries_struct,
        "invalid": invalid_val,
        "tp": tp_struct,
        "trailing": {
            "enabled": True,
            "anchor": "HL 15m",
            "offset_atr": 0.6,
        },
        "time_exit": {
            "enabled": True,
            "ttl_min": 240,
            "reason": "Stagnan > 4 jam",
        },
        "buyback": buyback,
        "macro_gate": {
            **_macro_gate(),
            "macro_bias": macro_bias,
        },
        "metrics": {
            "rr_min": float(plan.get("rr_min", 0.0) or 0.0),
            "tick_ok": True,
            "macro_score": macro_score,
            "macro_score_threshold": macro_threshold,
        },
        "round_numbers": _round_numbers(entries_struct[0]["price"]) if entries_struct else [],
        "notes": _macro_notes(),
        "warnings": [],
        "tf_base": "1h",
        "ringkas_teknis": bias,
        "invalids": {
            "m5": _f(plan.get("invalid_tactical_5m")),
            "m15": _f(plan.get("invalid_soft_15m")),
            "h1": _f(plan.get("invalid_hard_1h")) or invalid_val,
            "h4": _f(plan.get("invalid_struct_4h")),
        },
    }

    if atr15 is not None:
        spot2["metrics"]["atr15"] = float(atr15)

    if macro_score < macro_threshold:
        spot2["warnings"].append("Macro score < threshold; gunakan mode range (RR) & TP cepat.")
    if float(plan.get("rr_min", 0.0) or 0.0) < 1.8:
        spot2["warnings"].append("RR < 1.8 — pertimbangkan perketat invalid atau kurangi ukuran.")

    # Jalankan validator SPOT II agar konsisten dengan jalur LLM
    try:
        v = validate_spot2(spot2)
        spot2 = v.get("fixes") or spot2
    except Exception:
        pass
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


def build_mtf_summary(bundle, feat: "Features", plan: dict | None = None) -> dict:
    """Bangun ringkasan MTF ringkas untuk UI (non-JSON di FE).
    Field level_zona/skenario/catatan diisi singkat sesuai blueprint.
    """
    out: dict = {"trend_utama": ""}
    # Ambil referensi S/R & overlay opsional dari plan bila ada
    sr = dict((plan or {}).get("sr") or {})
    sup = list((plan or {}).get("support") or sr.get("support") or [])
    res = list((plan or {}).get("resistance") or sr.get("resistance") or [])
    fvg = (plan or {}).get("fvg") or []
    zones = (plan or {}).get("sd_zones") or []
    invs = {
        "5m": (plan or {}).get("invalid_tactical_5m"),
        "15m": (plan or {}).get("invalid_soft_15m"),
        "1h": (plan or {}).get("invalid_hard_1h") or (plan or {}).get("invalid"),
        "4h": (plan or {}).get("invalid_struct_4h"),
    }
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

        # Level & Zona singkat
        try:
            s1, s2 = (sup + [None, None])[:2]
            r1, r2 = (res + [None, None])[:2]
            lv_txt = "S/R: " + \
                (" · ".join([f"{s1}" if s1 is not None else "-", f"{s2}" if s2 is not None else "-"])) + \
                " / " + (" · ".join([f"{r1}" if r1 is not None else "-", f"{r2}" if r2 is not None else "-"]))
            fvg_cnt = len([x for x in fvg if x])
            z_cnt = len([z for z in zones if z])
            if fvg_cnt:
                lv_txt += f"; FVG:{fvg_cnt}"
            if z_cnt:
                lv_txt += f"; SD:{z_cnt}"
        except Exception:
            lv_txt = ""
        # Skenario cepat (heuristik sederhana PB/BO + invalid lokal jika ada)
        inv_local = invs.get(tf)
        try:
            is_bo_bias = (plan or {}).get("mode", "PB").upper() == "BO"
        except Exception:
            is_bo_bias = False
        if is_bo_bias:
            sk = f"Micro‑BO di atas R1; invalid lokal: {inv_local if inv_local is not None else '-'}"
        else:
            sk = f"PB cepat dekat EMA20; invalid lokal: {inv_local if inv_local is not None else '-'}"

        out[tf.replace("m", "m").replace("h", "h")] = {
            "tren_momentum": f"{ema_stack}; {rsi_line}; {macd_line}; {bb_line}; {atr_line}",
            "level_zona": lv_txt,
            "skenario": sk,
            "catatan": "Periksa reaksi di S/R terdekat; gunakan konfirmasi wick/volume.",
        }
    # trend utama sederhana dari H1/H4
    try:
        h1 = out.get("1h", {})
        h4 = out.get("4h", {})
        out["trend_utama"] = ("Bias utama: " + (h1.get("tren_momentum") or "") + " | " + (h4.get("tren_momentum") or "")).strip()
    except Exception:
        out["trend_utama"] = ""
    return out

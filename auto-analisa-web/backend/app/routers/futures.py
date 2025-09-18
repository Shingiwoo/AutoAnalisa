from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db
from app.auth import require_user
from app.models import Analysis, FuturesSignalsCache, Settings
from app.services.market import fetch_bundle
from app.services.rules import Features, score_symbol
from app.services.planner import build_plan_async, build_spot2_from_plan
from app.services.futures import latest_signals, fetch_leverage_bracket
from app.services.sessions import btc_wib_buckets
from app.services.validator_futures import validate_futures
from app.services.rounding import round_futures_prices
from app.services.llm import should_use_llm, ask_llm
from app.services.usage import get_today_usage, inc_usage
from app.services.budget import get_or_init_settings, add_usage, check_budget_and_maybe_off
from sqlalchemy import select, desc
import os, json, time
from app.models import LLMVerification, Analysis

router = APIRouter(prefix="/api/analyses", tags=["futures"])


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


@router.get("/{symbol}/futures")
async def get_futures_plan(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    # Feature-flag
    s = await db.get(Settings, 1)
    # if no row id=1, fallback to reading via helper (avoiding import cycle)
    if not s:
        from app.services.budget import get_or_init_settings
        s = await get_or_init_settings(db)
    if not getattr(s, "enable_futures", False):
        raise HTTPException(404, "Futures dinonaktifkan oleh admin")

    # Build a baseline spot plan and adapt to futures format
    bundle = await fetch_bundle(symbol, ("4h", "1h", "15m", "5m"))
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    base_plan = await build_plan_async(db, bundle, feat, score, "auto")
    spot2 = await build_spot2_from_plan(db, symbol.upper(), base_plan)
    # Pick representative values
    rjb = dict(spot2.get("rencana_jual_beli") or {})
    entries = [(_f((e.get("range") or [None])[0]), float(e.get("weight") or 0.0), (e.get("type") or "PB")) for e in (rjb.get("entries") or [])]
    tp_nodes = [(t.get("name") or f"TP{i+1}", _f((t.get("range") or [None])[0])) for i, t in enumerate(spot2.get("tp") or [])]
    # map spot2 invalids if available
    inv_map = dict(spot2.get("invalids") or {})
    invalids = {
        "tactical_5m": _f(inv_map.get("m5") if inv_map else rjb.get("invalid")),
        "soft_15m": _f(inv_map.get("m15")) if inv_map else None,
        "hard_1h": _f(inv_map.get("h1") if inv_map else rjb.get("invalid")),
        "struct_4h": _f(inv_map.get("h4")) if inv_map else None,
    }
    # risk and guard defaults
    lev_min = int(getattr(s, "futures_leverage_min", 3) or 3)
    lev_max = int(getattr(s, "futures_leverage_max", 10) or 10)
    risk_pct = float(getattr(s, "futures_risk_per_trade_pct", 0.5) or 0.5)
    liq_buf_k = float(getattr(s, "futures_liq_buffer_k_atr15m", 0.5) or 0.5)
    lev = max(lev_min, min(lev_max, 5))

    # Signals cache (best-effort, empty in this skeleton)
    q = await db.execute(select(FuturesSignalsCache).where(FuturesSignalsCache.symbol == symbol.upper()).order_by(FuturesSignalsCache.created_at.desc()))
    sig = q.scalars().first()
    # Auto-refresh sinyal bila kosong atau stale (>15 menit)
    try:
        from datetime import datetime, timezone, timedelta
        stale = True
        if sig and getattr(sig, "created_at", None):
            age = datetime.now(timezone.utc) - sig.created_at.replace(tzinfo=timezone.utc) if sig.created_at.tzinfo is None else datetime.now(timezone.utc) - sig.created_at
            stale = age > timedelta(minutes=15)
        if (not sig) or stale:
            from app.services.futures import refresh_signals_cache
            sig = await refresh_signals_cache(db, symbol.upper())
    except Exception:
        pass
    futures_signals = {
        "funding": {"now": getattr(sig, "funding_now", None), "next": getattr(sig, "funding_next", None), "time": getattr(sig, "next_funding_time", None)},
        "oi": {"now": getattr(sig, "oi_now", None), "d1": getattr(sig, "oi_d1", None)},
        "lsr": {"accounts": getattr(sig, "lsr_accounts", None), "positions": getattr(sig, "lsr_positions", None)},
        "basis": {"now": getattr(sig, "basis_now", None)},
        "taker_delta": {"m5": getattr(sig, "taker_delta_m5", None), "m15": getattr(sig, "taker_delta_m15", None), "h1": getattr(sig, "taker_delta_h1", None)},
    }

    # Side heuristic sederhana (trend 1H): LONG bila ema5>ema20>ema50; else SHORT
    side = "LONG"
    try:
        df1h = bundle.get("1h")
        last = df1h.iloc[-1]
        if not (float(getattr(last, "ema5", 0)) > float(getattr(last, "ema20", 0)) > float(getattr(last, "ema50", 0))):
            side = "SHORT"
    except Exception:
        side = "LONG"

    # Perkiraan harga likuidasi (linear perp, isolated) dengan mmr bracket pertama bila tersedia
    try:
        e0 = entries[0][0] if entries and entries[0][0] is not None else None
        liq_est = None
        if e0 is not None and lev:
            mmr = 0.0
            try:
                lb = await fetch_leverage_bracket(symbol)
                mmr = float((lb or {}).get("mmr") or 0.0)
            except Exception:
                mmr = 0.0
            if side == "LONG":
                liq_est = float(e0) * (1.0 - 1.0/float(lev) + mmr)
            else:
                liq_est = float(e0) * (1.0 + 1.0/float(lev) - mmr)
    except Exception:
        liq_est = None

    # Jam pantau WIB dari buckets signifikan
    try:
        buckets = await btc_wib_buckets(days=120, timeframe="1h")
        jam_pantau = [b["hour"] for b in (buckets or [])]
    except Exception:
        jam_pantau = []

    # Hitung buffer absolut dari ATR15m
    try:
        atr15 = float(bundle["15m"].iloc[-1].atr14)
    except Exception:
        atr15 = 0.0
    buf_abs = float(atr15) * float(liq_buf_k)

    fut = {
        "version": 1,
        "symbol": symbol.upper(),
        "contract": "PERP",
        "side": side,
        "tf_base": "15m",
        "bias": base_plan.get("bias", ""),
        "support": base_plan.get("support", [])[:2],
        "resistance": base_plan.get("resistance", [])[:2],
        "mode": (base_plan.get("mode") or "PB").upper(),
        "entries": [ {"range": [e or None, e or None], "weight": w, "type": t} for (e,w,t) in entries ],
        "tp": [ {"name": name, "range": [val, val], "reduce_only_pct": (40 if i == 0 else 60)} for i,(name,val) in enumerate(tp_nodes) if val is not None ],
        "invalids": invalids,
        "leverage_suggested": {"isolated": True, "x": lev},
        "risk": {"risk_per_trade_pct": risk_pct, "rr_min": ">=1.5", "fee_bp": 3, "slippage_bp": 2, "liq_price_est": liq_est, "liq_buffer_pct": f">={liq_buf_k} * ATR15m", "liq_buffer_abs": buf_abs, "max_addons": 1, "pyramiding": "on_retest", "funding_window_min": int(getattr(s, "futures_funding_avoid_minutes", 10) or 10), "funding_threshold_bp": float(getattr(s, "futures_funding_threshold_bp", 3.0) or 3.0), "funding_alert_enabled": bool(getattr(s, "futures_funding_alert_enabled", True)), "funding_alert_window_min": int(getattr(s, "futures_funding_alert_window_min", 30) or 30)},
        "futures_signals": futures_signals,
        "mtf_summary": spot2.get("mtf_summary") or {},
        "jam_pantau_wib": jam_pantau,
        "notes": [],
    }
    # Bulatkan harga ke tick size dan validasi guard sebelum dikirim
    try:
        fut = round_futures_prices(symbol, fut)
        v = validate_futures(fut)
        fut = v.get("fixes") or fut
    except Exception:
        pass
    return fut


@router.post("/{aid}/futures/verify")
async def verify_futures_llm(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    a = await db.get(Analysis, aid)
    if not a:
        raise HTTPException(404, "Not found")
    if a.user_id != user.id and getattr(user, "role", "user") != "admin":
        raise HTTPException(403, "Forbidden")
    # guards LLM use
    allowed, reason = await should_use_llm(db)
    if not allowed:
        raise HTTPException(409, detail={
            "error_code": "llm_disabled",
            "message": (reason or "LLM nonaktif"),
        })
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(409, detail={
            "error_code": "server_config",
            "message": "LLM belum dikonfigurasi: OPENAI_API_KEY belum diisi.",
        })
    sset = await get_or_init_settings(db)
    lim_fut = int(getattr(sset, "llm_daily_limit_futures", getattr(settings, "LLM_DAILY_LIMIT", 40)) or 40)
    today = await get_today_usage(db, user_id=user.id, kind="futures", limit_override=lim_fut)
    if today["remaining"] <= 0:
        raise HTTPException(409, detail={
            "error_code": "quota_exceeded",
            "message": "Limit harian LLM tercapai untuk akun ini.",
        })

    # build baseline futures JSON
    # reuse the GET endpoint builder pieces
    symbol = a.symbol
    bundle = await fetch_bundle(symbol, ("4h", "1h", "15m", "5m"))
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    base_plan = await build_plan_async(db, bundle, feat, score, "auto")
    spot2 = await build_spot2_from_plan(db, symbol.upper(), base_plan)
    # map invalids, entries, tp etc similar to get_futures_plan
    # (reuse the function by calling endpoint logic would duplicate work; keep inline)
    rjb = dict(spot2.get("rencana_jual_beli") or {})
    entries = [((e.get("range") or [None])[0]) for e in (rjb.get("entries") or [])]
    tp_nodes = [(t.get("name") or f"TP{i+1}", (t.get("range") or [None])[0]) for i, t in enumerate(spot2.get("tp") or [])]
    inv_map = dict(spot2.get("invalids") or {})
    invalids = {
        "tactical_5m": inv_map.get("m5") if inv_map else rjb.get("invalid"),
        "soft_15m": inv_map.get("m15") if inv_map else None,
        "hard_1h": inv_map.get("h1") if inv_map else rjb.get("invalid"),
        "struct_4h": inv_map.get("h4") if inv_map else None,
    }
    s = await get_or_init_settings(db)
    lev = max(int(getattr(s, "futures_leverage_min", 3) or 3), min(int(getattr(s, "futures_leverage_max", 10) or 10), 5))
    futures_base = {
        "version": 1,
        "symbol": symbol.upper(),
        "contract": "PERP",
        "side": "LONG",
        "tf_base": "1h",
        "support": base_plan.get("support", [])[:2],
        "resistance": base_plan.get("resistance", [])[:2],
        "mode": (base_plan.get("mode") or "PB").upper(),
        "entries": [ {"range": [e, e], "weight": 0.5, "type": base_plan.get("mode", "PB")} for e in entries if isinstance(e,(int,float)) ],
        "tp": [ {"name": name, "range": [val, val], "reduce_only_pct": (40 if i==0 else 60)} for i,(name,val) in enumerate(tp_nodes) if isinstance(val,(int,float)) ],
        "invalids": invalids,
        "leverage_suggested": {"isolated": True, "x": lev},
        "risk": {"risk_per_trade_pct": float(getattr(s, "futures_risk_per_trade_pct", 0.5) or 0.5), "rr_min": ">=1.5", "fee_bp": 3, "slippage_bp": 2, "liq_price_est": None, "liq_buffer_pct": ">=0.5 * ATR15m", "max_addons": 1, "pyramiding": "on_retest", "funding_window_min": int(getattr(s, "futures_funding_avoid_minutes", 10) or 10), "funding_threshold_bp": float(getattr(s, "futures_funding_threshold_bp", 3.0) or 3.0) },
    }

    constraints = {
        "rr_min_required": 1.5,
        "tp_must_be_ascending": True,
        "reduce_only_sum": 100,
        "weights_sum": 1.0,
        "invalid_final_ge_liq_buffer": True,
        "funding_guard": True,
        "output_format": "FORMAT_ANALISA_FUTURES",
    }
    prompt = (
        "Validasi & rapikan rencana FUTURES berikut. Balas JSON object sesuai kontrak FUTURES: "
        "{ entries:[{range:[low,high], weight, type}], tp:[{name,range,reduce_only_pct}], invalids{tactical_5m,soft_15m,hard_1h,struct_4h}, "
        "leverage_suggested, risk{risk_per_trade_pct, rr_min, fee_bp, slippage_bp, liq_price_est}, notes }. "
        "Ikuti guardrails.\n"
        f"GUARDRAILS: {json.dumps(constraints, ensure_ascii=False)}\n"
        f"FUTURES_INPUT: {json.dumps(futures_base, ensure_ascii=False)}\n"
    )

    try:
        text, usage = ask_llm(prompt)
    except Exception:
        raise HTTPException(502, "Gagal mengakses LLM")

    verdict = "confirm"
    summary = text
    fut_json = {}
    try:
        parsed = json.loads(text)
        fut_json = parsed
        verdict = (parsed.get("verdict") or parsed.get("status") or verdict).lower()
        summary = parsed.get("summary") or summary
    except Exception:
        fut_json = futures_base

    # round & validate
    try:
        fut_json = round_futures_prices(symbol, fut_json)
    except Exception:
        pass
    v = validate_futures(fut_json)
    if not v.get("ok"):
        verdict = "tweak" if verdict == "confirm" else verdict
    fut_json = v.get("fixes") or fut_json

    # usage bookkeeping
    model = os.getenv("OPENAI_MODEL", "gpt-5-chat-latest")
    sset = await get_or_init_settings(db)
    prompt_toks = int(usage.get("prompt_tokens", 0)) if isinstance(usage, dict) else 0
    completion_toks = int(usage.get("completion_tokens", 0)) if isinstance(usage, dict) else 0
    try:
        await add_usage(db, user.id, model, prompt_toks, completion_toks, sset.input_usd_per_1k, sset.output_usd_per_1k)
        await check_budget_and_maybe_off(db)
    except Exception:
        pass
    try:
        in_price = float(os.getenv("LLM_PRICE_INPUT_USD_PER_MTOK", 0.625))
        out_price = float(os.getenv("LLM_PRICE_OUTPUT_USD_PER_MTOK", 5.0))
        usd_daily = (prompt_toks/1_000_000.0)*in_price + (completion_toks/1_000_000.0)*out_price
        await inc_usage(db, user_id=user.id, model=model, input_tokens=prompt_toks, output_tokens=completion_toks, cost_usd=usd_daily, add_call=True, kind="futures")
        await db.commit()
    except Exception:
        pass

    vr = LLMVerification(
        analysis_id=a.id,
        user_id=user.id,
        model=model,
        prompt_tokens=prompt_toks,
        completion_tokens=completion_toks,
        cost_usd=0.0,
        verdict=verdict,
        summary=summary,
        futures_json=fut_json,
        cached=False,
    )
    db.add(vr)
    await db.commit()
    await db.refresh(vr)
    return {
        "verification": {
            "id": vr.id,
            "analysis_id": vr.analysis_id,
            "verdict": vr.verdict,
            "summary": vr.summary,
            "futures_json": vr.futures_json,
            "created_at": vr.created_at,
            "cached": False,
        }
    }


@router.post("/{aid}/futures/apply-llm")
async def apply_futures_llm(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    a = await db.get(Analysis, aid)
    if not a:
        raise HTTPException(404, "Not found")
    if a.user_id != user.id and getattr(user, "role", "user") != "admin":
        raise HTTPException(403, "Forbidden")
    q = await db.execute(select(LLMVerification).where(LLMVerification.analysis_id == a.id).order_by(desc(LLMVerification.created_at)))
    last = q.scalars().first()
    if not last or not last.futures_json:
        raise HTTPException(409, detail={"error_code": "precondition", "message": "Belum ada hasil LLM Futures"})
    fut = last.futures_json
    try:
        fut = round_futures_prices(a.symbol, fut)
        v = validate_futures(fut)
        fut = v.get("fixes") or fut
    except Exception:
        pass
    # Simpan ke payload analysis untuk referensi FE mendatang
    p = dict(a.payload_json or {})
    p["futures"] = fut
    # Tandai overlays untuk sinkronisasi FE jika diperlukan (opsional)
    p.setdefault("overlays", {})
    try:
        p["overlays"]["futures_applied"] = True
    except Exception:
        pass
    a.payload_json = p
    await db.commit()
    await db.refresh(a)
    return {"ok": True, "analysis": {"id": a.id, "version": a.version, "payload": a.payload_json}}

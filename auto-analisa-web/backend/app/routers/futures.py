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
    bundle = await fetch_bundle(symbol, ("4h", "1h", "15m", "5m"), market="futures")
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
    # Build machine plan from current analysis (reuse get_futures_plan pieces)
    symbol = a.symbol
    bundle = await fetch_bundle(symbol, ("4h", "1h", "15m", "5m"))
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    base_plan = await build_plan_async(db, bundle, feat, score, "auto")
    spot2 = await build_spot2_from_plan(db, symbol.upper(), base_plan)
    rjb = dict(spot2.get("rencana_jual_beli") or {})
    def _first_or_none(r):
        try:
            return float((r or [None])[0])
        except Exception:
            return None
    entries_nums = [ _first_or_none(e.get("range")) for e in (rjb.get("entries") or []) ]
    entries_nums = [x for x in entries_nums if isinstance(x,(int,float))]
    tp_nums = [ _first_or_none(t.get("range")) for t in (spot2.get("tp") or []) ]
    tp_nums = [x for x in tp_nums if isinstance(x,(int,float))]
    inv_map = dict(spot2.get("invalids") or {})
    invalids = {
        "tactical_5m": inv_map.get("m5") if inv_map else rjb.get("invalid"),
        "soft_15m": inv_map.get("m15") if inv_map else None,
        "hard_1h": inv_map.get("h1") if inv_map else rjb.get("invalid"),
        "struct_4h": inv_map.get("h4") if inv_map else None,
    }
    s = await get_or_init_settings(db)
    lev_suggested = max(int(getattr(s, "futures_leverage_min", 3) or 3), min(int(getattr(s, "futures_leverage_max", 10) or 10), 5))
    plan_mesin = {"entries": entries_nums, "tp": tp_nums, "invalids": invalids, "risk": {"risk_per_trade_pct": float(getattr(s, "futures_risk_per_trade_pct", 0.5) or 0.5), "rr_min": 1.5}}
    # precision from ccxt
    import ccxt
    ex = ccxt.binanceusdm()
    ex.load_markets(reload=False)
    m = ex.market(symbol.upper().replace(":USDT","/USDT"))
    price_prec = m.get("precision",{}).get("price")
    tick = float(10 ** (-price_prec)) if isinstance(price_prec,int) and price_prec>0 else (float((m.get("limits",{}).get("price") or {}).get("min") or 0) or None)
    step = float((m.get("limits",{}).get("amount") or {}).get("min") or 0) or None
    quote_precision = m.get("info",{}).get("quotePrecision")
    try:
        quote_precision = int(quote_precision) if quote_precision is not None else None
    except Exception:
        quote_precision = None
    from app.routers.llm import VerifyBody, perform_verify
    vb = VerifyBody(symbol=symbol, trade_type="futures", tf_base="15m", plan_mesin=plan_mesin, lev_policy={"lev_max_symbol": None, "lev_default": lev_suggested}, precision={"tickSize": tick, "stepSize": step, "quotePrecision": quote_precision}, macro_context=None, ui_contract={"tp_ladder_pct": [40,60]})
    out = await perform_verify(db, user.id, vb)
    usage = out.get("_usage") or {}
    model = os.getenv("OPENAI_MODEL", "gpt-5-chat-latest")
    try:
        in_price = float(os.getenv("LLM_PRICE_INPUT_USD_PER_MTOK", 0.625))
        out_price = float(os.getenv("LLM_PRICE_OUTPUT_USD_PER_MTOK", 5.0))
        usd_daily = (int(usage.get("prompt_tokens") or 0)/1_000_000.0)*in_price + (int(usage.get("completion_tokens") or 0)/1_000_000.0)*out_price
        await inc_usage(db, user_id=user.id, model=model, input_tokens=int(usage.get("prompt_tokens") or 0), output_tokens=int(usage.get("completion_tokens") or 0), cost_usd=usd_daily, add_call=True, kind="futures")
        await db.commit()
    except Exception:
        pass
    vr = LLMVerification(
        analysis_id=a.id,
        user_id=user.id,
        model=model,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        cost_usd=0.0,
        verdict=(out.get("hasil_json") or {}).get("verdict") or "valid",
        summary=out.get("ringkas_naratif") or "",
        futures_json=out.get("hasil_json") or {},
        trade_type="futures",
        macro_snapshot=out.get("_macro_snapshot") or {},
        ui_contract={"tp_ladder_pct": (out.get("hasil_json") or {}).get("tp_ladder_pct") or [40,60]},
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
            "macro_snapshot": out.get("_macro_snapshot") or {},
            "ui_contract": {"tp_ladder_pct": (out.get("hasil_json") or {}).get("tp_ladder_pct") or [40,60]},
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


from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_db
from app.services.market import fetch_bundle
from app.services.rules import Features
from app.services.futures import latest_signals
from app.services.strategy_futures import build_plan_futures
from app.services.llm import should_use_llm
from app.services.usage import inc_usage, get_today_usage
from app.services.budget import get_or_init_settings, add_usage, check_budget_and_maybe_off
from app.auth import require_user
import os

router = APIRouter(prefix="/futures", tags=["futures"])

async def _build_futures(symbol: str, db: AsyncSession, user, use_llm: bool = False):
    bundle = await fetch_bundle(symbol, tfs=("4h","1h","15m","5m","1m"), market="futures")
    feat = Features(bundle); feat.enrich()
    sig = await latest_signals(db, symbol)
    allow_llm = False
    deny_reason = None
    if use_llm:
        try:
            allow_llm, deny_reason = await should_use_llm(db)
        except Exception:
            allow_llm, deny_reason = False, "LLM unavailable"
        # Per-user daily limit check for futures kind
        if allow_llm:
            try:
                sset = await get_or_init_settings(db)
                limit = int(getattr(sset, "llm_daily_limit_futures", 40) or 40)
                today = await get_today_usage(db, user_id=user.id, kind="futures", limit_override=limit)
                if int(today.get("remaining") or 0) <= 0:
                    allow_llm, deny_reason = False, "Limit harian LLM (futures) tercapai"
            except Exception:
                # if usage service fails, do not block, just proceed without LLM
                allow_llm, deny_reason = False, "Daily limit check gagal"
    plan = build_plan_futures(
        bundle, feat,
        side_hint="AUTO",
        fut_signals=sig,
        symbol=symbol,
        use_llm_fixes=bool(use_llm and allow_llm),
        profile="scalp",
    )
    try:
        swing_variant = build_plan_futures(
            bundle,
            feat,
            side_hint="AUTO",
            fut_signals=sig,
            symbol=symbol,
            use_llm_fixes=False,
            profile="swing",
        )
        if isinstance(plan, dict):
            plan.setdefault("variants", {})["swing"] = {k: v for k, v in swing_variant.items() if k != "_usage"}
    except Exception:
        pass
    # If LLM used, record token usage (both monthly budget and daily aggregator), then strip _usage from response
    usage = dict(plan.get("_usage") or {}) if isinstance(plan, dict) else {}
    if use_llm and allow_llm and usage:
        try:
            model = os.getenv("OPENAI_MODEL", "gpt-5-chat-latest")
            prompt_toks = int(usage.get("prompt_tokens") or 0)
            completion_toks = int(usage.get("completion_tokens") or 0)
            sset = await get_or_init_settings(db)
            # Monthly budget tracking (per 1k tokens)
            usd, _month_used = await add_usage(
                db,
                user_id=user.id,
                model=model,
                prompt_toks=prompt_toks,
                completion_toks=completion_toks,
                in_usd_per_1k=float(getattr(sset, "input_usd_per_1k", 0.005) or 0.005),
                out_usd_per_1k=float(getattr(sset, "output_usd_per_1k", 0.015) or 0.015),
            )
            await check_budget_and_maybe_off(db)
            # Daily aggregated usage (per MTOK)
            in_price = float(os.getenv("LLM_PRICE_INPUT_USD_PER_MTOK", getattr(sset, "input_usd_per_1k", 0.005) * 1000.0))
            out_price = float(os.getenv("LLM_PRICE_OUTPUT_USD_PER_MTOK", getattr(sset, "output_usd_per_1k", 0.015) * 1000.0))
            usd_daily = (prompt_toks / 1_000_000.0) * in_price + (completion_toks / 1_000_000.0) * out_price
            await inc_usage(
                db,
                user_id=user.id,
                model=model,
                input_tokens=prompt_toks,
                output_tokens=completion_toks,
                cost_usd=usd_daily,
                add_call=True,
                kind="futures",
            )
            await db.commit()
        except Exception:
            # best-effort accounting only
            pass
    # hide internal usage field from API response
    try:
        if isinstance(plan, dict) and "_usage" in plan:
            plan = dict(plan)
            plan.pop("_usage", None)
    except Exception:
        pass
    if use_llm and not allow_llm:
        try:
            plan.setdefault("notes", []).append(f"LLM off: {deny_reason}")
        except Exception:
            pass
    # return usage summary (non-sensitive) for FE observability
    # compute llm_used based on actual token usage
    total_tokens = int(usage.get("total_tokens") or (int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0))) if usage else 0
    llm_used_flag = bool(use_llm and allow_llm and total_tokens > 0)
    if use_llm and allow_llm and not llm_used_flag:
        try:
            plan.setdefault("notes", []).append("LLM tidak dijalankan atau tidak terkonfigurasi; gunakan plan mesin.")
        except Exception:
            pass
    return {
        "ok": True,
        "symbol": symbol.upper(),
        "plan": plan,
        "signals": sig,
        "llm_used": llm_used_flag,
        "usage": {"prompt_tokens": int(usage.get("prompt_tokens") or 0), "completion_tokens": int(usage.get("completion_tokens") or 0)} if (use_llm and allow_llm) else None,
    }


@router.get("/plan/{symbol}")
async def build_plan(symbol: str, db: AsyncSession = Depends(get_db), use_llm: bool = Query(False, description="Gunakan LLM fix-pass JSON strict"), user=Depends(require_user)):
    return await _build_futures(symbol, db, user, use_llm=use_llm)


@router.post("/analyze")
async def analyze(body: dict, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    symbol = (body.get("symbol") or "").upper()
    if not symbol:
        raise HTTPException(422, "symbol wajib diisi")
    use_llm = bool(body.get("use_llm") or False)
    return await _build_futures(symbol, db, user, use_llm=use_llm)


@router.post("/analyze-batch")
async def analyze_batch(body: dict, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    symbols = [str(s).upper() for s in (body.get("symbols") or []) if s]
    if not symbols:
        raise HTTPException(422, "symbols[] wajib diisi")
    use_llm = bool(body.get("use_llm") or False)
    results = []
    for sym in symbols:
        try:
            res = await _build_futures(sym, db, user, use_llm=use_llm)
        except Exception as e:
            res = {"ok": False, "symbol": sym, "error": str(e)}
        results.append(res)
    return {"ok": True, "count": len(results), "results": results}

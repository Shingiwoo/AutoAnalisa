from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.deps import get_db
from app.auth import require_user
from app.models import Analysis, Plan, LLMVerification, Settings
from app.services.budget import get_or_init_settings, add_usage, check_budget_and_maybe_off
from app.services.llm import should_use_llm, ask_llm
from app.services.usage import get_today_usage, inc_usage
from app.workers.analyze_worker import refresh_analysis_rules_only
from app.services.market import fetch_bundle
from app.main import locks
from app.services.validator import normalize_and_validate, validate_spot2
import os, json, time
from app.config import settings

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.get("")
async def list_analyses(status: str = "active", db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    if status == "active":
        q = await db.execute(
            select(Analysis).where(Analysis.user_id == user.id, Analysis.status == "active").order_by(Analysis.created_at.desc())
        )
        rows = q.scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "version": r.version,
                "payload": r.payload_json,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    else:
        q = await db.execute(
            select(Plan).where(Plan.user_id == user.id).order_by(Plan.created_at.desc())
        )
        rows = q.scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "version": r.version,
                "payload": r.payload_json,
                "created_at": r.created_at,
            }
            for r in rows
        ]


@router.post("/{aid}/save")
async def save_snapshot(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    a = await db.get(Analysis, aid)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Not found")
    # Create a snapshot in Plan table and keep current Analysis active
    snap = Plan(user_id=user.id, symbol=a.symbol, version=a.version, payload_json=a.payload_json)
    db.add(snap)
    await db.commit()
    return {"ok": True, "active_id": a.id}


@router.post("/{aid}/refresh")
async def refresh_rules(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    a = await db.get(Analysis, aid)
    if not a:
        raise HTTPException(404, "Not found")
    if a.user_id != user.id and getattr(user, "role", "user") != "admin":
        raise HTTPException(403, "Forbidden")
    # lightweight rate limit per analysis/user
    ok = await locks.acquire(f"rate:refresh:{user.id}:{aid}", ttl=5)
    if not ok:
        raise HTTPException(429, "Terlalu sering, coba lagi sebentar.")
    # Check invalid-breach against latest price before refreshing
    prev_payload = dict(a.payload_json or {})
    prev_invalidated = False
    try:
        prev_invalid = prev_payload.get("invalid")
        if isinstance(prev_invalid, (int, float)):
            # use latest close on 1h if available, fallback to 15m
            bundle = await fetch_bundle(a.symbol, ("1h", "15m"))
            last_close = None
            try:
                last_close = float(bundle["1h"].iloc[-1].close)
            except Exception:
                last_close = float(bundle["15m"].iloc[-1].close)
            if isinstance(last_close, float) and last_close < float(prev_invalid):
                prev_invalidated = True
                # Archive previous plan as snapshot for reference
                try:
                    snap = Plan(user_id=a.user_id, symbol=a.symbol, version=a.version, payload_json=prev_payload)
                    db.add(snap)
                    await db.commit()
                except Exception:
                    # best-effort; do not block refresh
                    pass
    except Exception:
        pass

    a = await refresh_analysis_rules_only(db, user, a)
    # Attach a brief notice if prior setup was invalidated
    if prev_invalidated:
        try:
            p = dict(a.payload_json or {})
            p["notice"] = "Setup sebelumnya invalid; rencana baru dibuat (v%d)." % int(a.version)
            a.payload_json = p
            await db.commit()
        except Exception:
            pass
    return {
        "prev_invalidated": prev_invalidated,
        "analysis": {
            "id": a.id,
            "symbol": a.symbol,
            "version": a.version,
            "payload": a.payload_json,
            "created_at": a.created_at,
        }
    }


@router.post("/{aid}/verify")
async def verify_llm(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    a = await db.get(Analysis, aid)
    if not a:
        raise HTTPException(404, "Not found")
    if a.user_id != user.id and getattr(user, "role", "user") != "admin":
        raise HTTPException(403, "Forbidden")
    # rate-limit per user and analysis
    if not await locks.acquire(f"rate:verify:{user.id}", ttl=10):
        raise HTTPException(429, "Terlalu sering, coba lagi sebentar.")
    if not await locks.acquire(f"rate:verify:{user.id}:{aid}", ttl=15):
        raise HTTPException(429, "Terlalu sering, coba lagi sebentar.")

    # check LLM toggle and budget
    allowed, reason = await should_use_llm(db)
    if not allowed:
        raise HTTPException(409, detail=(reason or "LLM sedang nonaktif."))
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(409, detail="LLM belum dikonfigurasi: OPENAI_API_KEY belum diisi.")

    # Enforce daily per-user limit before using cache or calling LLM
    today = await get_today_usage(db, user_id=user.id)
    if today["remaining"] <= 0:
        raise HTTPException(409, detail="Limit harian LLM tercapai untuk akun ini.")

    # cache: reuse last verification if within TTL (still counts a call)
    cache_ttl = int(os.getenv("LLM_CACHE_TTL_S", "900"))
    q = await db.execute(
        select(LLMVerification).where(LLMVerification.analysis_id == a.id).order_by(desc(LLMVerification.created_at))
    )
    last = q.scalars().first()
    now_ts = time.time()
    if last and (now_ts - last.created_at.timestamp()) <= cache_ttl:
        # Count this click against daily usage quota
        await inc_usage(
            db,
            user_id=user.id,
            model=os.getenv("OPENAI_MODEL", "gpt-5-chat-latest"),
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            add_call=True,
        )
        await db.commit()
        return {
            "verification": {
                "id": last.id,
                "analysis_id": last.analysis_id,
                "user_id": last.user_id,
                "model": last.model,
                "prompt_tokens": last.prompt_tokens,
                "completion_tokens": last.completion_tokens,
                "cost_usd": last.cost_usd,
                "verdict": last.verdict,
                "summary": last.summary,
                "suggestions": last.suggestions,
                "fundamentals": last.fundamentals,
                "created_at": last.created_at,
                "cached": True,
            }
        }

    # prepare snapshot for LLM
    p = a.payload_json or {}
    snap = {
        "symbol": a.symbol,
        "version": a.version,
        "score": p.get("score"),
        "bias": p.get("bias"),
        "entries": p.get("entries", []),
        "tp": p.get("tp", []),
        "invalid": p.get("invalid"),
        "weights": p.get("weights", []),
        "support": p.get("support", []),
        "resistance": p.get("resistance", []),
    }
    prompt = (
        "Validasi rencana trading berikut, balas JSON dengan kunci: "
        "verdict (confirm|tweak|warning|reject), summary (1-2 kalimat), "
        "suggestions {entries:[], tp:[], invalid: <number|null>, notes:[]}, fundamentals: {bullets: []}.\n"
        f"DATA: {json.dumps(snap, ensure_ascii=False)}"
    )
    s = await get_or_init_settings(db)
    # Enforce daily per-user limit before calling LLM
    today = await get_today_usage(db, user_id=user.id)
    if today["remaining"] <= 0:
        raise HTTPException(409, detail="Limit harian LLM tercapai untuk akun ini.")

    try:
        text, usage = ask_llm(prompt)
    except Exception as e:  # pragma: no cover
        raise HTTPException(502, detail="Gagal mengakses LLM. Coba lagi nanti.")

    # try parse JSON content
    verdict = "confirm"
    summary = text
    suggestions = {}
    fundamentals = {}
    try:
        parsed = json.loads(text)
        # SPOT II expected
        if parsed.get("rencana_jual_beli") and parsed.get("tp"):
            spot2 = parsed
        else:
            # backward: accept wrapper with spot2
            spot2 = parsed.get("spot2") or {}
        # validate spot2 and apply light fixes
        v = validate_spot2(spot2)
        if not v.get("ok"):
            # still proceed but mark verdict if necessary
            verdict = "tweak" if verdict == "confirm" else verdict
        spot2 = v.get("fixes") or spot2
        verdict = (parsed.get("verdict") or parsed.get("status") or verdict).lower()
        summary = parsed.get("summary") or parsed.get("ringkas") or summary
        suggestions = parsed.get("suggestions") or {}
        fundamentals = parsed.get("fundamentals") or {}
    except Exception:
        # Enforce strict JSON contract per blueprint
        raise HTTPException(502, detail="LLM tidak mengembalikan JSON valid")

    # sanitize suggestions by validating a candidate plan built from current + suggestions
    try:
        cand = dict(snap)
        if isinstance(suggestions, dict):
            if isinstance(suggestions.get("entries"), list):
                cand["entries"] = suggestions.get("entries")
            if isinstance(suggestions.get("tp"), list):
                cand["tp"] = suggestions.get("tp")
            if suggestions.get("invalid") is not None:
                cand["invalid"] = suggestions.get("invalid")
        cand2, warns = normalize_and_validate(cand)
        # reflect sanitized values back into suggestions so FE diff uses normalized numbers
        suggestions = dict(suggestions or {})
        suggestions["entries"] = cand2.get("entries", cand.get("entries"))
        suggestions["tp"] = cand2.get("tp", cand.get("tp"))
        if cand2.get("invalid") is not None:
            suggestions["invalid"] = cand2.get("invalid")
        # degrade verdict if rr_min too low
        if float(cand2.get("rr_min", 0.0)) < 1.2 and verdict == "confirm":
            verdict = "warning"
            summary = (summary or "") + " (rr_min<1.2)"
    except Exception:
        pass

    # record usage and insert row
    model = os.getenv("OPENAI_MODEL", "gpt-5-chat-latest")
    prompt_toks = int((usage or {}).get("prompt_tokens", 0))
    completion_toks = int((usage or {}).get("completion_tokens", 0))
    usd, _month_used = await add_usage(
        db,
        user.id,
        model,
        prompt_toks,
        completion_toks,
        s.input_usd_per_1k,
        s.output_usd_per_1k,
    )
    await check_budget_and_maybe_off(db)

    # Also update daily aggregated usage with per-MTOK pricing
    try:
        in_price = float(getattr(settings, "LLM_PRICE_INPUT_USD_PER_MTOK", 0.625))
        out_price = float(getattr(settings, "LLM_PRICE_OUTPUT_USD_PER_MTOK", 5.0))
        usd_daily = (prompt_toks / 1_000_000.0) * in_price + (completion_toks / 1_000_000.0) * out_price
        await inc_usage(
            db,
            user_id=user.id,
            model=model,
            input_tokens=prompt_toks,
            output_tokens=completion_toks,
            cost_usd=usd_daily,
            add_call=True,
        )
        await db.commit()
    except Exception:
        # best-effort; do not block main flow
        pass

    vr = LLMVerification(
        analysis_id=a.id,
        user_id=user.id,
        model=model,
        prompt_tokens=prompt_toks,
        completion_tokens=completion_toks,
        cost_usd=float(usd or 0.0),
        verdict=verdict,
        summary=summary,
        suggestions=suggestions,
        fundamentals=fundamentals,
        spot2_json=spot2 if 'spot2' in locals() else {},
        cached=False,
    )
    db.add(vr)
    await db.commit()
    await db.refresh(vr)

    # also enrich analysis payload with last verification short summary for UI convenience (optional)
    try:
        a.payload_json = dict(p or {})
        a.payload_json["llm_verification"] = {
            "id": vr.id,
            "verdict": vr.verdict,
            "summary": vr.summary,
            "at": vr.created_at.isoformat(),
        }
        await db.commit()
    except Exception:
        pass

    return {
        "verification": {
            "id": vr.id,
            "analysis_id": vr.analysis_id,
            "user_id": vr.user_id,
            "model": vr.model,
            "prompt_tokens": vr.prompt_tokens,
            "completion_tokens": vr.completion_tokens,
            "cost_usd": vr.cost_usd,
            "verdict": vr.verdict,
            "summary": vr.summary,
            "suggestions": vr.suggestions,
            "fundamentals": vr.fundamentals,
            "created_at": vr.created_at,
            "cached": False,
        }
    }


@router.post("/{aid}/apply-llm")
async def apply_llm(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    a = await db.get(Analysis, aid)
    if not a:
        raise HTTPException(404, "Not found")
    if a.user_id != user.id and getattr(user, "role", "user") != "admin":
        raise HTTPException(403, "Forbidden")
    # get last verification
    q = await db.execute(
        select(LLMVerification).where(LLMVerification.analysis_id == a.id).order_by(desc(LLMVerification.created_at))
    )
    last = q.scalars().first()
    if not last or not last.spot2_json:
        raise HTTPException(409, "Belum ada hasil LLM berbentuk SPOT II")
    # apply spot2 to payload, keep legacy fields for FE compatibility
    p = a.payload_json or {}
    # write spot2
    p["spot2"] = last.spot2_json
    # also reflect to legacy overlays arrays to sync chart immediately
    try:
        rjb = (last.spot2_json or {}).get("rencana_jual_beli", {})
        entries = [ (e.get("range") or [None])[0] for e in (rjb.get("entries") or []) ]
        tp_arr = [ (t.get("range") or [None])[0] for t in (last.spot2_json.get("tp") or []) ]
        invalid = rjb.get("invalid")
        p["entries"] = [float(x) for x in entries if isinstance(x,(int,float))]
        p["tp"] = [float(x) for x in tp_arr if isinstance(x,(int,float))]
        if isinstance(invalid,(int,float)):
            p["invalid"] = float(invalid)
        # set weights if provided
        wts = [ float(e.get("weight") or 0.0) for e in (rjb.get("entries") or []) ]
        if wts and len(wts)==len(p["entries"]):
            p["weights"] = wts
    except Exception:
        pass
    # Mark overlays state
    p.setdefault("overlays", {})
    try:
        p["overlays"]["applied"] = True
        p["overlays"]["ghost"] = False
    except Exception:
        pass
    a.payload_json = p
    await db.commit()
    await db.refresh(a)
    return {"ok": True, "analysis": {"id": a.id, "version": a.version, "payload": a.payload_json}}

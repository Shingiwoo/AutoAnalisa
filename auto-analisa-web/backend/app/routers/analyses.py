from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.deps import get_db
from app.auth import require_user
from app.models import Analysis, Plan, LLMVerification, Settings
from app.services.budget import get_or_init_settings, add_usage, check_budget_and_maybe_off
from app.services.planner import build_spot2_from_plan
from app.services.llm import should_use_llm, ask_llm
from app.services.usage import get_today_usage, inc_usage
from app.workers.analyze_worker import refresh_analysis_rules_only
from app.services.market import fetch_bundle
from app.main import locks
from app.services.validator import normalize_and_validate, validate_spot2
from app.services.rounding import round_spot2_prices
import os, json, time
from app.config import settings

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def _norm_trade_type(value: str | None) -> str:
    try:
        if str(value).lower() == "futures":
            return "futures"
    except Exception:
        pass
    return "spot"


@router.get("")
async def list_analyses(status: str = "active", trade_type: str | None = None, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    if status == "active":
        conds = [Analysis.user_id == user.id, Analysis.status == "active"]
        if trade_type:
            tt = _norm_trade_type(trade_type)
            conds.append(func.coalesce(Analysis.trade_type, "spot") == tt)
        q = await db.execute(select(Analysis).where(*conds).order_by(Analysis.created_at.desc()))
        rows = q.scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "trade_type": getattr(r, "trade_type", "spot"),
                "version": r.version,
                "payload": r.payload_json,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    else:
        conds = [Plan.user_id == user.id]
        if trade_type:
            tt = _norm_trade_type(trade_type)
            conds.append(func.coalesce(Plan.trade_type, "spot") == tt)
        q = await db.execute(select(Plan).where(*conds).order_by(Plan.created_at.desc()))
        rows = q.scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "trade_type": getattr(r, "trade_type", "spot"),
                "version": r.version,
                "payload": r.payload_json,
                "created_at": r.created_at,
            }
            for r in rows
        ]


@router.get("/latest")
async def latest(symbol: str, trade_type: str = "spot", db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    """Return latest active analysis for a symbol filtered by trade_type.

    Used by FE to ensure Spot vs Futures data isolation.
    """
    tt = _norm_trade_type(trade_type)
    conds = [
        Analysis.user_id == user.id,
        Analysis.symbol == symbol.upper(),
        Analysis.status == "active",
        func.coalesce(Analysis.trade_type, "spot") == tt,
    ]
    q = await db.execute(select(Analysis).where(*conds).order_by(desc(Analysis.created_at)))
    a = q.scalars().first()
    if not a:
        raise HTTPException(404, "Not found")
    return {
        "id": a.id,
        "symbol": a.symbol,
        "trade_type": getattr(a, "trade_type", "spot"),
        "version": a.version,
        "payload": a.payload_json,
        "created_at": a.created_at,
    }

@router.post("/{aid}/save")
async def save_snapshot(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    a = await db.get(Analysis, aid)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Not found")
    # Create a snapshot in Plan table and keep current Analysis active
    snap = Plan(
        user_id=user.id,
        symbol=a.symbol,
        trade_type=getattr(a, "trade_type", "spot"),
        version=a.version,
        payload_json=a.payload_json,
    )
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
    prev_soft_breach = False
    try:
        prev_invalid = prev_payload.get("invalid")
        inv_soft = prev_payload.get("invalid_soft_15m")
        inv_hard = prev_payload.get("invalid_hard_1h") or prev_invalid
        # use latest close on 1h if available, fallback to 15m
        bundle = await fetch_bundle(a.symbol, ("1h", "15m"))
        last_close = None
        try:
            last_close = float(bundle["1h"].iloc[-1].close)
        except Exception:
            last_close = float(bundle["15m"].iloc[-1].close)
        if isinstance(last_close, float):
            # hard-breach check
            if isinstance(inv_hard, (int, float)) and last_close <= float(inv_hard):
                prev_invalidated = True
                # Archive previous plan as snapshot for reference
                try:
                    snap = Plan(
                        user_id=a.user_id,
                        symbol=a.symbol,
                        trade_type=getattr(a, "trade_type", "spot"),
                        version=a.version,
                        payload_json=prev_payload,
                    )
                    db.add(snap)
                    await db.commit()
                except Exception:
                    # best-effort; do not block refresh
                    pass
            # soft-breach check (only mark if not hard)
            elif isinstance(inv_soft, (int, float)) and last_close <= float(inv_soft):
                prev_soft_breach = True
    except Exception:
        pass

    a = await refresh_analysis_rules_only(db, user, a)
    # Attach a brief notice if prior setup was invalidated or soft-breach
    if prev_invalidated:
        try:
            p = dict(a.payload_json or {})
            p["notice"] = f"Setup {a.symbol} sebelumnya invalid; rencana baru dibuat (v{int(a.version)})."
            a.payload_json = p
            await db.commit()
        except Exception:
            pass
    elif prev_soft_breach:
        try:
            p = dict(a.payload_json or {})
            p["notice"] = "Rawan — cek ulang 15m (soft-breach)."
            a.payload_json = p
            await db.commit()
        except Exception:
            pass
    return {
        "prev_invalidated": prev_invalidated,
        "prev_soft_breach": prev_soft_breach,
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
        raise HTTPException(429, detail={
            "error_code": "rate_limited",
            "message": "Terlalu sering, coba lagi sebentar.",
            "retry_hint": "Coba lagi setelah ±10 detik."
        })
    if not await locks.acquire(f"rate:verify:{user.id}:{aid}", ttl=15):
        raise HTTPException(429, detail={
            "error_code": "rate_limited",
            "message": "Terlalu sering untuk analisa ini, coba lagi sebentar.",
            "retry_hint": "Coba lagi setelah ±15 detik."
        })

    # check LLM toggle and budget
    allowed, reason = await should_use_llm(db)
    if not allowed:
        raise HTTPException(409, detail={
            "error_code": "llm_disabled",
            "message": (reason or "LLM sedang nonaktif."),
            "retry_hint": "Aktifkan LLM di Admin atau tunggu sampai budget reset."
        })
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(409, detail={
            "error_code": "server_config",
            "message": "LLM belum dikonfigurasi: OPENAI_API_KEY belum diisi.",
            "retry_hint": "Set OPENAI_API_KEY dan ulangi."
        })

    # Enforce daily per-user limit before using cache or calling LLM
    # daily limit spot
    sset = await get_or_init_settings(db)
    lim_spot = int(getattr(sset, "llm_daily_limit_spot", getattr(settings, "LLM_DAILY_LIMIT", 40)) or 40)
    today = await get_today_usage(db, user_id=user.id, kind="spot", limit_override=lim_spot)
    if today["remaining"] <= 0:
        raise HTTPException(409, detail={
            "error_code": "quota_exceeded",
            "message": "Limit harian LLM tercapai untuk akun ini.",
            "retry_hint": "Coba lagi besok atau hubungi admin untuk menambah kuota."
        })

    # cache: reuse last verification if within TTL (still counts a call)
    cache_ttl = int(os.getenv("LLM_CACHE_TTL_S", "900"))
    q = await db.execute(
        select(LLMVerification).where(LLMVerification.analysis_id == a.id).order_by(desc(LLMVerification.created_at))
    )
    last = q.scalars().first()
    now_ts = time.time()
    if last and (now_ts - last.created_at.timestamp()) <= cache_ttl:
        # Jika analisa sudah diperbarui setelah verifikasi terakhir, abaikan cache
        try:
            if getattr(a, "created_at", None) and last.created_at < a.created_at:
                last = None
        except Exception:
            pass
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
            kind="spot",
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
                "spot2_json": last.spot2_json,
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
        "invalids": {
            "m5": p.get("invalid_tactical_5m"),
            "m15": p.get("invalid_soft_15m"),
            "h1": p.get("invalid_hard_1h") or p.get("invalid"),
            "h4": p.get("invalid_struct_4h"),
        },
        "mtf_summary": p.get("mtf_summary", {}),
    }
    # Build SPOT II basis (from existing payload or rules)
    spot2_base = (p.get("spot2") if isinstance(p, dict) else None) or {}
    if not spot2_base:
        try:
            spot2_base = await build_spot2_from_plan(db, a.symbol, p)
        except Exception:
            spot2_base = {}

    # Instruct LLM Tuner (fase 1) untuk menghasilkan SPOT-II+ terbaru
    constraints = {
        "rr_min_required": 1.6,
        "tp_must_be_ascending": True,
        "entries_require_price": True,
        "tp_qty_pct_sum": 100,
        "invalid_below_entries": True,
        "tp_min_count": 3,
        "buyback_min": 3,
        "macro_gate_keys": ["avoid_red", "prefer_wib", "avoid_wib", "session_refs"],
        "output_format": "FORMAT_ANALISA_SPOT_II_PLUS",
    }
    tuner_prompt = (
        "Anda adalah LLM Tuner SPOT. Perbaiki angka rencana agar sesuai guardrails dan format SPOT-II+. "
        "Balas dengan JSON objek yang memuat field wajib: symbol, trade_type, regime{regime,confidence}, mode, bias, "
        "sr{support,resistance}, entries[{price,weight,type,note?}], invalid, tp[{name,price,qty_pct,logic}], trailing{enabled,anchor,offset_atr}, "
        "time_exit{enabled,ttl_min,reason}, buyback[{name,range,note}], macro_gate{avoid_red,prefer_wib,avoid_wib,session_refs,sop_partial_on_red}, "
        "metrics{rr_min,tick_ok,macro_score,macro_score_threshold}, notes[], warnings[]. Pastikan qty_pct total 100 dan TP naik.\n"
        f"GUARDRAILS: {json.dumps(constraints, ensure_ascii=False)}\n"
        f"SPOT2_INPUT: {json.dumps(spot2_base, ensure_ascii=False)}\n"
        f"SNAPSHOT_MTF: {json.dumps(snap, ensure_ascii=False)}"
    )
    s = await get_or_init_settings(db)

    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}

    try:
        tuner_text, usage_tuner = ask_llm(tuner_prompt)
    except Exception as e:  # pragma: no cover
        raise HTTPException(502, detail={
            "error_code": "server_error",
            "message": "Gagal mengakses LLM. Coba lagi nanti.",
            "retry_hint": "Periksa koneksi atau konfigurasi LLM."
        })

    def _parse_spot2_payload(raw):
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        if isinstance(parsed, dict):
            if parsed.get("entries") and parsed.get("tp"):
                return parsed
            if isinstance(parsed.get("spot2"), dict):
                return parsed.get("spot2")
        return None

    usage_total["prompt_tokens"] += int((usage_tuner or {}).get("prompt_tokens", 0))
    usage_total["completion_tokens"] += int((usage_tuner or {}).get("completion_tokens", 0))

    spot2_tuned = _parse_spot2_payload(tuner_text) or None
    tuner_ok = bool(spot2_tuned and isinstance(spot2_tuned.get("entries"), list) and spot2_tuned.get("entries") and isinstance(spot2_tuned.get("tp"), list) and spot2_tuned.get("tp"))
    if not tuner_ok:
        spot2_tuned = None

    # Fase 2: Verifikator menilai hasil tuner
    verifier_prompt = (
        "Anda adalah LLM Verifikator. Nilai apakah rencana SPOT-II+ berikut sudah sesuai guardrails. "
        "Balas JSON {verdict:""confirm|tweak|reject"", reasons:[...], fix?:SPOT2_OBJECT}. Jika perlu perbaikan minor, isi fix dengan objek SPOT-II+.\n"
        f"GUARDRAILS: {json.dumps(constraints, ensure_ascii=False)}\n"
        f"PLAN_TUNED: {json.dumps(spot2_tuned or spot2_base, ensure_ascii=False)}"
    )

    try:
        verifier_text, usage_ver = ask_llm(verifier_prompt)
    except Exception:
        verifier_text, usage_ver = (json.dumps({"verdict": "confirm", "reasons": []}), {"prompt_tokens": 0, "completion_tokens": 0})

    usage_total["prompt_tokens"] += int((usage_ver or {}).get("prompt_tokens", 0))
    usage_total["completion_tokens"] += int((usage_ver or {}).get("completion_tokens", 0))

    verdict_payload = {}
    try:
        verdict_payload = json.loads(verifier_text)
    except Exception:
        verdict_payload = {}

    fix_candidate = _parse_spot2_payload(json.dumps(verdict_payload.get("fix") or {})) if verdict_payload.get("fix") else None
    if fix_candidate:
        spot2_candidate = fix_candidate
    else:
        spot2_candidate = spot2_tuned or spot2_base

    if (not tuner_ok) and not fix_candidate:
        raise HTTPException(422, detail={
            "error_code": "schema_invalid",
            "message": "LLM Tuner tidak mengembalikan SPOT-II+ lengkap.",
            "retry_hint": "Periksa prompt atau ulangi verifikasi.",
        })

    text = tuner_text  # preserve last LLM text for legacy summary fallback
    usage = usage_total
    parsed_verdict = verdict_payload

    verdict = str(parsed_verdict.get("verdict") or "confirm").lower()
    if verdict not in {"confirm", "tweak", "warning", "reject"}:
        verdict = "confirm"
    summary = parsed_verdict.get("summary") or "Rencana hasil tuner."
    suggestions = parsed_verdict.get("suggestions") or {}
    fundamentals = parsed_verdict.get("fundamentals") or {}
    reasons = parsed_verdict.get("reasons") or []
    if reasons and verdict == "confirm":
        verdict = "tweak"
        summary = summary + " (cek catatan verifikator)"
    spot2 = spot2_candidate or {}
    raw_invalid = spot2.get("invalid")
    if not (isinstance(spot2.get("entries"), list) and spot2.get("entries") and isinstance(spot2.get("tp"), list) and spot2.get("tp")):
        raise HTTPException(422, detail={
            "error_code": "schema_invalid",
            "message": "LLM tidak menyertakan entries/tp yang wajib.",
            "retry_hint": "Ulangi verifikasi; pastikan format SPOT-II+ lengkap.",
        })
    v = validate_spot2(spot2)
    if not v.get("ok") and verdict == "confirm":
        verdict = "tweak"
    spot2 = v.get("fixes") or spot2
    try:
        spot2 = round_spot2_prices(a.symbol, spot2)
        v2 = validate_spot2(spot2)
        spot2 = v2.get("fixes") or spot2
    except Exception:
        pass

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

    try:
        spot2_payload = locals().get("spot2")
        if isinstance(spot2_payload, dict):
            if spot2_payload.get("invalid") is None:
                candidate = raw_invalid
                if candidate is None:
                    base_invalid = None
                    try:
                        base_invalid = float((spot2_base or {}).get("invalid"))
                    except Exception:
                        base_invalid = ((spot2_base or {}).get("rencana_jual_beli") or {}).get("invalid")
                    candidate = base_invalid
                if candidate is not None:
                    try:
                        spot2_payload["invalid"] = float(candidate)
                    except Exception:
                        spot2_payload["invalid"] = candidate
            # Back-compat: perbarui rencana_jual_beli jika masih ada struktur lama
            if isinstance(spot2_payload.get("rencana_jual_beli"), dict):
                rjb_final = dict(spot2_payload.get("rencana_jual_beli") or {})
                if rjb_final.get("invalid") is None and spot2_payload.get("invalid") is not None:
                    rjb_final["invalid"] = spot2_payload.get("invalid")
                spot2_payload["rencana_jual_beli"] = rjb_final
            spot2 = spot2_payload
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
            kind="spot",
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
            "spot2_json": vr.spot2_json,
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
        raise HTTPException(409, detail={
            "error_code": "precondition",
            "message": "Belum ada hasil LLM berbentuk SPOT II",
        })
    # Round & validate sebelum apply (konsisten dengan verify)
    try:
        s2 = round_spot2_prices(a.symbol, last.spot2_json)
        v = validate_spot2(s2)
        last.spot2_json = v.get("fixes") or s2
    except Exception:
        pass
    # Guard: pastikan SPOT II memiliki entries & tp
    try:
        entries_list = list((last.spot2_json or {}).get("entries") or [])
        if not entries_list:
            entries_list = list(((last.spot2_json or {}).get("rencana_jual_beli") or {}).get("entries") or [])
        tps = list((last.spot2_json or {}).get("tp") or [])
        if not entries_list or not tps:
            raise HTTPException(422, detail={
                "error_code": "schema_invalid",
                "message": "SPOT II dari LLM tidak lengkap (entries/tp kosong).",
                "retry_hint": "Ulangi verifikasi dan pastikan format sesuai.",
            })
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, detail="SPOT II dari LLM tidak valid.")
    # apply spot2 to payload, keep legacy fields for FE compatibility
    p = a.payload_json or {}
    # write spot2
    p["spot2"] = last.spot2_json
    # also reflect to legacy overlays arrays to sync chart immediately
    try:
        spot2_struct = dict(last.spot2_json or {})
        entries_struct = list(spot2_struct.get("entries") or [])
        if not entries_struct and isinstance(spot2_struct.get("rencana_jual_beli"), dict):
            entries_struct = list((spot2_struct.get("rencana_jual_beli") or {}).get("entries") or [])
        entries = []
        for e in entries_struct:
            if e.get("price") is not None:
                entries.append(e.get("price"))
            elif (e.get("range") or [None])[0] is not None:
                entries.append((e.get("range") or [None])[0])
        tp_arr = []
        for t in (spot2_struct.get("tp") or []):
            if t.get("price") is not None:
                tp_arr.append(t.get("price"))
            elif (t.get("range") or [None])[0] is not None:
                tp_arr.append((t.get("range") or [None])[0])
        invalid = spot2_struct.get("invalid")
        if invalid is None and isinstance(spot2_struct.get("rencana_jual_beli"), dict):
            invalid = (spot2_struct.get("rencana_jual_beli") or {}).get("invalid")
        p["entries"] = [float(x) for x in entries if isinstance(x,(int,float))]
        p["tp"] = [float(x) for x in tp_arr if isinstance(x,(int,float))]
        if isinstance(invalid,(int,float)):
            p["invalid"] = float(invalid)
            # sinkronkan invalid bertingkat (fallback simple bila LLM hanya kembalikan 1 invalid)
            try:
                inv = float(invalid)
                p["invalid_hard_1h"] = inv
                # gunakan buffer sederhana
                buf = max(abs(inv) * 1e-4, 0.0)
                p["invalid_soft_15m"] = round(inv + buf, 6)
                p["invalid_tactical_5m"] = round(inv + buf * 0.5, 6)
            except Exception:
                pass
        # set weights if provided
        wts = [ float(e.get("weight") or 0.0) for e in entries_struct ]
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
@router.get("/{symbol}/spot")
async def get_spot(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    q = await db.execute(
        select(Analysis)
        .where(
            Analysis.user_id == user.id,
            Analysis.symbol == symbol.upper(),
            Analysis.status == "active",
            func.coalesce(Analysis.trade_type, "spot") == "spot",
        )
        .order_by(desc(Analysis.created_at))
    )
    a = q.scalars().first()
    if not a:
        raise HTTPException(404, "Not found")
    return {
        "id": a.id,
        "symbol": a.symbol,
        "version": a.version,
        "payload": a.payload_json,
        "created_at": a.created_at,
    }

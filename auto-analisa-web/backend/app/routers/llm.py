from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from app.deps import get_db
from app.auth import require_user
from app.services.llm import should_use_llm, ask_llm_messages
from app.services.usage import get_today_usage
from app.services.budget import get_or_init_settings
from app.services.usage import inc_usage
from app.models import LLMVerification
from app.services.advisor_futures import auto_suggest_futures
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os, json


def _round_to_tick(x: float, tick: float) -> float:
    try:
        if tick and tick > 0:
            n = round(x / tick)
            return float(n * tick)
        return float(x)
    except Exception:
        return float(x)


def _unique_with_tol(vals: List[float], eps: float) -> List[float]:
    s = sorted([float(v) for v in vals if isinstance(v, (int, float))])
    out: List[float] = []
    for v in s:
        if not out or abs(v - out[-1]) > eps:
            out.append(v)
    return out


def _wib_window(now: Optional[datetime] = None) -> str:
    jkt = ZoneInfo("Asia/Jakarta")
    now = now or datetime.now(timezone.utc)
    w = now.astimezone(jkt)
    hm = w.hour + w.minute / 60.0
    # HIJAU: 01:00–08:00, 20:30–23:00; MERAH: 22:00–01:00; NETRAL: lainnya
    if (1.0 <= hm <= 8.0) or (20.5 <= hm <= 23.0):
        return "HIJAU"
    if (22.0 <= hm) or (hm < 1.0):
        return "MERAH"
    return "NETRAL"


class VerifyBody(BaseModel):
    symbol: str
    trade_type: str = Field("futures")
    tf_base: str = Field("15m")
    plan_mesin: Dict[str, Any]
    lev_policy: Optional[Dict[str, Any]] = None
    precision: Dict[str, Any]
    macro_context: Optional[Dict[str, Any]] = None
    ui_contract: Optional[Dict[str, Any]] = None


async def perform_verify(db: AsyncSession, user_id: str, body: VerifyBody) -> Dict[str, Any]:
    # Pre-check LLM availability and quota for futures
    allowed, reason = await should_use_llm(db)
    if not allowed:
        raise HTTPException(409, detail={"error_code": "llm_disabled", "message": (reason or "LLM nonaktif"), "retry_hint": "Aktifkan LLM di Admin atau tunggu reset budget"})
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(409, detail={"error_code": "server_config", "message": "OPENAI_API_KEY belum diisi", "retry_hint": "Set env dan ulangi"})
    sset = await get_or_init_settings(db)
    limit = int(getattr(sset, "llm_daily_limit_futures", 40) or 40)
    today = await get_today_usage(db, user_id=user_id, kind="futures", limit_override=limit)
    if today["remaining"] <= 0:
        raise HTTPException(409, detail={"error_code": "quota_exceeded", "message": "Limit harian LLM (futures) tercapai", "retry_hint": "Coba lagi besok"})

    symbol = body.symbol.upper()
    pm = dict(body.plan_mesin or {})
    prec = dict(body.precision or {})
    tick = float(prec.get("tickSize") or 0.0) if prec.get("tickSize") else None
    step = float(prec.get("stepSize") or 0.0) if prec.get("stepSize") else None
    quote_prec = None
    try:
        qp = prec.get("quotePrecision")
        quote_prec = int(qp) if qp is not None else None
    except Exception:
        quote_prec = None

    # Server macro snapshot
    jkt = ZoneInfo("Asia/Jakarta")
    now = datetime.now(timezone.utc)
    mctx = dict(body.macro_context or {})
    mctx.setdefault("wib_window", _wib_window(now))
    # minutes_to_funding best-effort: get from FuturesSignalsCache if available
    try:
        from app.services.futures import latest_signals
        sig = await latest_signals(db, symbol)
        nft = sig.get("funding", {}).get("time")
        if nft:
            try:
                t = datetime.fromisoformat(nft.replace("Z", "+00:00"))
                dtm = int(max(0, (t - now).total_seconds() // 60))
                mctx.setdefault("minutes_to_funding", dtm)
            except Exception:
                pass
    except Exception:
        pass
    # other fields may be provided by client: dxy_trend, pboc

    # Leverage policy
    lev_pol = dict(body.lev_policy or {})
    lev_default = int(lev_pol.get("lev_default") or 0)
    lev_max = int(lev_pol.get("lev_max_symbol") or 0)
    try:
        if not lev_max:
            from app.services.futures import fetch_leverage_bracket
            br = await fetch_leverage_bracket(symbol)
            if br and br.get("lev_max"):
                lev_max = int(br.get("lev_max"))
        if not lev_max:
            lev_max = int(os.getenv("FUTURES_DEFAULT_LEV_MAX", "50"))
    except Exception:
        lev_max = int(os.getenv("FUTURES_DEFAULT_LEV_MAX", "50"))
    # Expected default per policy: 50% of max, capped at 50 if lev_max > 100
    exp_default = min(50, int((lev_max or 0) * 0.5)) if lev_max else lev_default or 0
    violates_policy = bool(lev_default and exp_default and (lev_default != exp_default))

    # Build LLM prompt
    sys = (
        "Anda adalah verifikator rencana PERPETUAL FUTURES. Tugas Anda: memeriksa rencana mesin dan memberi catatan ringkas. "
        "Jangan membuat level baru. Jika angka tidak sesuai tick/step, sarankan pembulatan (tandai ui_flags.need_rounding=true). "
        "Hormati kebijakan leverage (default 50% dari max). Konteks makro WIB hanya untuk catatan/guard, tidak mengubah entries/TP/invalid."
    )
    user = {
        "symbol": symbol,
        "trade_type": body.trade_type or "futures",
        "tf_base": body.tf_base or "15m",
        "plan_mesin": pm,
        "lev_policy": {"lev_max_symbol": lev_max, "lev_default": lev_default},
        "precision": {"tickSize": tick, "stepSize": step, "quotePrecision": quote_prec},
        "macro_context": mctx,
        "ui_contract": dict(body.ui_contract or {}),
    }
    asst = (
        "Kembalikan ringkas_naratif (<=8 kalimat) dan hasil_json sesuai skema. "
        "hasil_json harus berisi: verdict (valid|tweak|reject), reasons[], entries[], tp[], tp_ladder_pct[], invalids{tactical_5m,soft_15m,hard_1h,struct_4h}, "
        "risk{risk_per_trade_pct, rr_min}, leverage{lev_default, violates_lev_policy}, macro_notes[], ui_flags{need_rounding, dup_values_cleaned}. "
        "Jangan menambah level baru; pastikan TP ascending dan RR>=rr_min."
    )
    text, usage = ask_llm_messages([
        {"role": "system", "content": sys},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        {"role": "assistant", "content": asst},
    ])

    ringkas = ""
    hasil = {}
    try:
        parsed = json.loads(text or "{}")
        ringkas = parsed.get("ringkas_naratif") or ""
        hasil = dict(parsed.get("hasil_json") or {})
    except Exception:
        ringkas = (text or "").strip()[:300]
        hasil = {}

    # Server-side normalization
    entries = [float(x) for x in (hasil.get("entries") or pm.get("entries") or []) if isinstance(x, (int, float))]
    tp = [float(x) for x in (hasil.get("tp") or pm.get("tp") or []) if isinstance(x, (int, float))]
    invalids = dict(hasil.get("invalids") or pm.get("invalids") or {})
    need_rounding = False
    if tick and tick > 0:
        r_entries = [_round_to_tick(x, tick) for x in entries]
        r_tp = [_round_to_tick(x, tick) for x in tp]
        r_invalids = {}
        for k in ["tactical_5m", "soft_15m", "hard_1h", "struct_4h"]:
            v = invalids.get(k)
            r_invalids[k] = _round_to_tick(float(v), tick) if isinstance(v, (int, float)) else v
        need_rounding = (r_entries != entries) or (r_tp != tp) or any((r_invalids.get(k) != invalids.get(k)) for k in r_invalids)
        entries, tp, invalids = r_entries, r_tp, r_invalids
    # De-dupe
    eps = (tick or 0.0) / 2.0 if tick else 0.0
    clean_entries = _unique_with_tol(entries, eps) if entries else []
    clean_tp = _unique_with_tol(tp, eps) if tp else []
    dup_cleaned = (clean_entries != entries) or (clean_tp != tp)
    entries, tp = clean_entries, clean_tp

    # TP ascending validation and RR min
    verdict = (hasil.get("verdict") or "valid").lower()
    reasons = list(hasil.get("reasons") or [])
    if tp != sorted(tp):
        verdict = "tweak" if verdict == "valid" else verdict
        reasons.append("TP tidak ascending; dinormalisasi server")
        tp = sorted(tp)
    rr_min = None
    try:
        rr_min = float(((hasil.get("risk") or {}).get("rr_min")) or ((pm.get("risk") or {}).get("rr_min")) or 0)
    except Exception:
        rr_min = None

    # Server-side advisor fallback bila LLM minim saran
    try:
        macro = dict(body.macro_context or {})
        fut_sig = dict(macro.get("futures_signals") or {})
        mtf_sum = dict(macro.get("mtf_summary") or {})
        # side tebak: TP > entry → LONG, sebaliknya SHORT
        side_guess = "LONG"
        try:
            side_guess = "LONG" if (tp and entries and float(tp[0]) >= float(entries[0])) else "SHORT"
        except Exception:
            pass
        plan_for_advisor = {
            "side": side_guess,
            "entries": entries,
            "tp": tp,
            "invalids": {"hard_1h": invalids.get("hard_1h") or invalids.get("h1")},
            "risk": (hasil.get("risk") or pm.get("risk") or {}),
        }
        advisor = auto_suggest_futures(
            plan_for_advisor,
            fut_sig,
            mtf_sum,
            precision=prec,
            rr_min_threshold=1.5,
            funding_thresh_bp=float(os.getenv("FUTURES_FUNDING_WARNING_BP", "3.0")),
        )
        sev = int(advisor.get("severity") or 0)
        if sev >= 1:
            reasons = reasons + (advisor.get("reasons") or [])
        # apply fixes bila severity>=2 atau LLM diam (tidak memberi fixes eksplisit)
        if sev >= 2:
            if advisor.get("verdict") and verdict in ("valid", "warning"):
                verdict = advisor.get("verdict")
            fixes = advisor.get("fixes") or {}
            if isinstance(fixes.get("entries"), list) and fixes["entries"]:
                entries = [float(x) for x in fixes["entries"] if isinstance(x, (int, float))]
            inv_fix = fixes.get("invalids") or {}
            if isinstance(inv_fix.get("hard_1h"), (int, float)):
                invalids["hard_1h"] = float(inv_fix.get("hard_1h"))
    except Exception:
        pass

    # Leverage policy check
    lev_obj = dict(hasil.get("leverage") or {})
    lev_obj.setdefault("lev_default", lev_default)
    if exp_default:
        lev_obj["violates_lev_policy"] = violates_policy
    # Macro notes: ensure list
    macro_notes = list(hasil.get("macro_notes") or [])
    if mctx.get("wib_window"):
        macro_notes = macro_notes[:3]
    ui_flags = dict(hasil.get("ui_flags") or {})
    ui_flags["need_rounding"] = bool(ui_flags.get("need_rounding") or need_rounding)
    ui_flags["dup_values_cleaned"] = bool(ui_flags.get("dup_values_cleaned") or dup_cleaned)
    # tp ladder pct passthrough from contract if provided
    tp_ladder_pct = hasil.get("tp_ladder_pct") or (body.ui_contract or {}).get("tp_ladder_pct") or []

    hasil_out = {
        "verdict": verdict,
        "reasons": reasons,
        "entries": entries,
        "tp": tp,
        "tp_ladder_pct": tp_ladder_pct,
        "invalids": invalids,
        "risk": pm.get("risk") or hasil.get("risk") or {},
        "leverage": lev_obj,
        "macro_notes": macro_notes,
        "ui_flags": ui_flags,
    }

    return {
        "ringkas_naratif": ringkas,
        "hasil_json": hasil_out,
        "_usage": usage,
        "_macro_snapshot": mctx,
        "_lev_policy": {"lev_max_symbol": lev_max, "lev_default": lev_default, "expected_default": exp_default},
    }


router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/quota")
async def quota(db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    s = await get_or_init_settings(db)
    limit_spot = int(getattr(s, "llm_daily_limit_spot", 40) or 40)
    limit_fut = int(getattr(s, "llm_daily_limit_futures", 40) or 40)
    usage_spot = await get_today_usage(db, user_id=user.id, kind="spot", limit_override=limit_spot)
    usage_fut = await get_today_usage(db, user_id=user.id, kind="futures", limit_override=limit_fut)
    allowed, _ = await should_use_llm(db)
    # For backward UI, report spot values in top-level and include futures_* fields for richer clients
    llm_enabled = bool(allowed) and usage_spot["remaining"] > 0
    return {
        "limit": usage_spot["limit"],
        "remaining": usage_spot["remaining"],
        "calls": usage_spot["calls"],
        "llm_enabled": llm_enabled,
        "futures_limit": usage_fut["limit"],
        "futures_remaining": usage_fut["remaining"],
        "futures_calls": usage_fut["calls"],
    }


@router.post("/verify")
async def verify(body: VerifyBody, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    # Perform verification and handle usage bookkeeping
    out = await perform_verify(db, user.id, body)
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
    # Persist lightweight verification row for audit (analysis_id nullable)
    try:
        vr = LLMVerification(
            analysis_id=None,  # standalone verify
            user_id=user.id,
            model=model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            cost_usd=0.0,
            verdict=(out.get("hasil_json") or {}).get("verdict") or "valid",
            summary=out.get("ringkas_naratif") or "",
            futures_json=out.get("hasil_json") or {},
            trade_type=body.trade_type or "futures",
            macro_snapshot=out.get("_macro_snapshot") or {},
            ui_contract=body.ui_contract or {},
            cached=False,
        )
        db.add(vr)
        await db.commit()
    except Exception:
        pass
    # Return contract
    return {"ringkas_naratif": out.get("ringkas_naratif"), "hasil_json": out.get("hasil_json")}

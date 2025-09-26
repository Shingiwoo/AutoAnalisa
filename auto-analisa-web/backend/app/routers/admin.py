from fastapi import APIRouter, Depends, HTTPException
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.deps import get_db
from app.config import settings as app_settings
from app.auth import get_current_user
from app.models import Settings, ApiUsage, PasswordChangeRequest, User, MacroDaily
from app.services.budget import (
    get_or_init_settings,
    month_key,
    add_usage,
    check_budget_and_maybe_off,
)
from app.auth import hash_pw
from app import services
from datetime import datetime, timezone
from app.services.parity import fvg_parity_stats, zones_parity_stats
from app.services import futures as futures_svc
import pandas as pd


router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    s = await get_or_init_settings(db)
    # Provide both legacy and aliased fields for FE compatibility
    llm_model = (os.getenv("OPENAI_MODEL", "gpt-5-chat-latest"))
    return {
        # legacy
        "use_llm": s.use_llm,
        "registration_enabled": s.registration_enabled,
        "budget_monthly_usd": s.budget_monthly_usd,
        "auto_off_at_budget": s.auto_off_at_budget,
        "budget_used_usd": s.budget_used_usd,
        "input_usd_per_1k": s.input_usd_per_1k,
        "output_usd_per_1k": s.output_usd_per_1k,
        "month_key": month_key(),
        "max_users": getattr(s, "max_users", 4),
        "enable_fvg": getattr(s, "enable_fvg", False),
        "enable_supply_demand": getattr(s, "enable_supply_demand", False),
        "fvg_use_bodies": getattr(s, "fvg_use_bodies", False),
        "fvg_fill_rule": getattr(s, "fvg_fill_rule", "any_touch"),
        "sd_max_base": getattr(s, "sd_max_base", 3),
        "sd_body_ratio": getattr(s, "sd_body_ratio", 0.33),
        "sd_min_departure": getattr(s, "sd_min_departure", 1.5),
        "fvg_threshold_pct": getattr(s, "fvg_threshold_pct", 0.0),
        "fvg_threshold_auto": getattr(s, "fvg_threshold_auto", False),
        "fvg_tf": getattr(s, "fvg_tf", "15m"),
        "sd_mode": getattr(s, "sd_mode", "swing"),
        "sd_vol_div": getattr(s, "sd_vol_div", 20),
        "sd_vol_threshold_pct": getattr(s, "sd_vol_threshold_pct", 10.0),
        "show_sessions_hint": getattr(s, "show_sessions_hint", True),
        "default_weight_profile": getattr(s, "default_weight_profile", "DCA"),
        "llm_daily_limit_spot": getattr(s, "llm_daily_limit_spot", 40),
        "llm_daily_limit_futures": getattr(s, "llm_daily_limit_futures", 40),
        # futures
        "enable_futures": getattr(s, "enable_futures", False),
        "futures_leverage_min": getattr(s, "futures_leverage_min", 3),
        "futures_leverage_max": getattr(s, "futures_leverage_max", 10),
        "futures_risk_per_trade_pct": getattr(s, "futures_risk_per_trade_pct", 0.5),
        "futures_funding_threshold_bp": getattr(s, "futures_funding_threshold_bp", 3.0),
        "futures_funding_avoid_minutes": getattr(s, "futures_funding_avoid_minutes", 10),
        "futures_liq_buffer_k_atr15m": getattr(s, "futures_liq_buffer_k_atr15m", 0.5),
        "futures_default_weight_profile": getattr(s, "futures_default_weight_profile", "DCA"),
        "futures_funding_alert_enabled": getattr(s, "futures_funding_alert_enabled", True),
        "futures_funding_alert_window_min": getattr(s, "futures_funding_alert_window_min", 30),
        # new aliases
        "llm_enabled": s.use_llm,
        "llm_model": llm_model,
        "llm_limit_monthly_usd": s.budget_monthly_usd,
        "llm_spend_monthly_usd": s.budget_used_usd,
    }


def _apply_settings_payload(s, payload: dict):
    """Apply settings from payload.
    Prefer canonical keys over aliases when both are present to avoid overrides.
    """
    # Map destination attribute -> list of accepted input keys (canonical first)
    sources = {
        "use_llm": ["use_llm", "llm_enabled"],
        "registration_enabled": ["registration_enabled"],
        "max_users": ["max_users"],
        "enable_fvg": ["enable_fvg"],
        "enable_supply_demand": ["enable_supply_demand"],
        "fvg_use_bodies": ["fvg_use_bodies"],
        "fvg_fill_rule": ["fvg_fill_rule"],
        "fvg_threshold_pct": ["fvg_threshold_pct"],
        "fvg_threshold_auto": ["fvg_threshold_auto"],
        "fvg_tf": ["fvg_tf"],
        "sd_max_base": ["sd_max_base"],
        "sd_body_ratio": ["sd_body_ratio"],
        "sd_min_departure": ["sd_min_departure"],
        "sd_mode": ["sd_mode"],
        "sd_vol_div": ["sd_vol_div"],
        "sd_vol_threshold_pct": ["sd_vol_threshold_pct"],
        "show_sessions_hint": ["show_sessions_hint"],
        "default_weight_profile": ["default_weight_profile"],
        # futures
        "enable_futures": ["enable_futures"],
        "futures_leverage_min": ["futures_leverage_min"],
        "futures_leverage_max": ["futures_leverage_max"],
        "futures_risk_per_trade_pct": ["futures_risk_per_trade_pct"],
        "futures_funding_threshold_bp": ["futures_funding_threshold_bp"],
        "futures_funding_avoid_minutes": ["futures_funding_avoid_minutes"],
        "futures_liq_buffer_k_atr15m": ["futures_liq_buffer_k_atr15m"],
        "futures_default_weight_profile": ["futures_default_weight_profile"],
        "futures_funding_alert_enabled": ["futures_funding_alert_enabled"],
        "futures_funding_alert_window_min": ["futures_funding_alert_window_min"],
        "budget_monthly_usd": ["budget_monthly_usd", "llm_limit_monthly_usd"],
        "auto_off_at_budget": ["auto_off_at_budget"],
        "input_usd_per_1k": ["input_usd_per_1k"],
        "output_usd_per_1k": ["output_usd_per_1k"],
        "llm_daily_limit_spot": ["llm_daily_limit_spot"],
        "llm_daily_limit_futures": ["llm_daily_limit_futures"],
    }
    bool_fields = {"use_llm", "registration_enabled", "auto_off_at_budget", "show_sessions_hint", "enable_futures", "futures_funding_alert_enabled"}
    bool_fields |= {"enable_fvg", "enable_supply_demand", "fvg_use_bodies"}
    float_fields = {"budget_monthly_usd", "input_usd_per_1k", "output_usd_per_1k", "sd_body_ratio", "sd_min_departure", "fvg_threshold_pct", "sd_vol_threshold_pct", "futures_risk_per_trade_pct", "futures_funding_threshold_bp", "futures_liq_buffer_k_atr15m"}
    int_fields = {"max_users", "sd_max_base", "sd_vol_div", "futures_leverage_min", "futures_leverage_max", "futures_funding_avoid_minutes", "futures_funding_alert_window_min", "llm_daily_limit_spot", "llm_daily_limit_futures"}

    for attr, keys in sources.items():
        # pick the first present key
        chosen = None
        for k in keys:
            if k in payload:
                chosen = payload[k]
                break
        if chosen is None:
            continue
        v = chosen
        try:
            if attr in bool_fields:
                # ensure proper bool for common representations
                if isinstance(v, str):
                    v = v.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
                else:
                    v = bool(v)
            elif attr in float_fields:
                v = float(v)
                if attr == "budget_monthly_usd" and v < 0:
                    v = 0.0
                if attr in {"input_usd_per_1k", "output_usd_per_1k"} and v < 0:
                    v = 0.0
            elif attr in int_fields:
                v = int(v)
                if v < 1:
                    v = 1
        except Exception:
            # ignore bad types; keep current value
            continue
        setattr(s, attr, v)
    # touch updated_at
    try:
        s.updated_at = datetime.utcnow()
    except Exception:
        pass


@router.post("/settings")
async def update_settings(payload: dict, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    s = await get_or_init_settings(db)
    _apply_settings_payload(s, payload)
    await db.commit()
    # Return the latest snapshot to help clients reflect instantly
    return {
        "ok": True,
        "settings": {
            "use_llm": s.use_llm,
            "registration_enabled": s.registration_enabled,
            "max_users": getattr(s, "max_users", 4),
            "enable_fvg": getattr(s, "enable_fvg", False),
            "enable_supply_demand": getattr(s, "enable_supply_demand", False),
            "fvg_use_bodies": getattr(s, "fvg_use_bodies", False),
            "fvg_fill_rule": getattr(s, "fvg_fill_rule", "any_touch"),
            "sd_max_base": getattr(s, "sd_max_base", 3),
            "sd_body_ratio": getattr(s, "sd_body_ratio", 0.33),
            "sd_min_departure": getattr(s, "sd_min_departure", 1.5),
            "fvg_threshold_pct": getattr(s, "fvg_threshold_pct", 0.0),
            "fvg_threshold_auto": getattr(s, "fvg_threshold_auto", False),
            "fvg_tf": getattr(s, "fvg_tf", "15m"),
            "sd_mode": getattr(s, "sd_mode", "swing"),
            "sd_vol_div": getattr(s, "sd_vol_div", 20),
            "sd_vol_threshold_pct": getattr(s, "sd_vol_threshold_pct", 10.0),
            "show_sessions_hint": getattr(s, "show_sessions_hint", True),
            "default_weight_profile": getattr(s, "default_weight_profile", "DCA"),
            "budget_monthly_usd": s.budget_monthly_usd,
            "auto_off_at_budget": s.auto_off_at_budget,
            "input_usd_per_1k": s.input_usd_per_1k,
            "output_usd_per_1k": s.output_usd_per_1k,
            "budget_used_usd": s.budget_used_usd,
            "llm_daily_limit_spot": getattr(s, "llm_daily_limit_spot", 40),
            "llm_daily_limit_futures": getattr(s, "llm_daily_limit_futures", 40),
        },
    }


@router.put("/settings")
async def put_settings(payload: dict, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    s = await get_or_init_settings(db)
    _apply_settings_payload(s, payload)
    await db.commit()
    return {
        "llm_enabled": s.use_llm,
        "llm_model": os.getenv("OPENAI_MODEL", "gpt-5-chat-latest"),
        "llm_limit_monthly_usd": s.budget_monthly_usd,
        "llm_spend_monthly_usd": s.budget_used_usd,
        "max_users": getattr(s, "max_users", 4),
        "enable_fvg": getattr(s, "enable_fvg", False),
        "enable_supply_demand": getattr(s, "enable_supply_demand", False),
        "fvg_use_bodies": getattr(s, "fvg_use_bodies", False),
        "fvg_fill_rule": getattr(s, "fvg_fill_rule", "any_touch"),
        "sd_max_base": getattr(s, "sd_max_base", 3),
        "sd_body_ratio": getattr(s, "sd_body_ratio", 0.33),
        "sd_min_departure": getattr(s, "sd_min_departure", 1.5),
        "fvg_threshold_pct": getattr(s, "fvg_threshold_pct", 0.0),
        "fvg_threshold_auto": getattr(s, "fvg_threshold_auto", False),
        "fvg_tf": getattr(s, "fvg_tf", "15m"),
        "sd_mode": getattr(s, "sd_mode", "swing"),
        "sd_vol_div": getattr(s, "sd_vol_div", 20),
        "sd_vol_threshold_pct": getattr(s, "sd_vol_threshold_pct", 10.0),
        "show_sessions_hint": getattr(s, "show_sessions_hint", True),
        "default_weight_profile": getattr(s, "default_weight_profile", "DCA"),
        "llm_daily_limit_spot": getattr(s, "llm_daily_limit_spot", 40),
        "llm_daily_limit_futures": getattr(s, "llm_daily_limit_futures", 40),
        # futures
        "enable_futures": getattr(s, "enable_futures", False),
        "futures_leverage_min": getattr(s, "futures_leverage_min", 3),
        "futures_leverage_max": getattr(s, "futures_leverage_max", 10),
        "futures_risk_per_trade_pct": getattr(s, "futures_risk_per_trade_pct", 0.5),
        "futures_funding_threshold_bp": getattr(s, "futures_funding_threshold_bp", 3.0),
        "futures_funding_avoid_minutes": getattr(s, "futures_funding_avoid_minutes", 10),
        "futures_liq_buffer_k_atr15m": getattr(s, "futures_liq_buffer_k_atr15m", 0.5),
        "futures_default_weight_profile": getattr(s, "futures_default_weight_profile", "DCA"),
        "futures_funding_alert_enabled": getattr(s, "futures_funding_alert_enabled", True),
        "futures_funding_alert_window_min": getattr(s, "futures_funding_alert_window_min", 30),
    }


@router.get("/usage")
async def usage(db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    mk = month_key()
    q = await db.execute(select(ApiUsage).where(ApiUsage.month_key == mk))
    rows = q.scalars().all()
    total = sum(r.usd_cost for r in rows)
    return {"month_key": mk, "count": len(rows), "total_usd": total}


@router.get("/password_requests")
async def list_pwd_requests(db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    q = await db.execute(select(PasswordChangeRequest).where(PasswordChangeRequest.status == "pending"))
    rows = q.scalars().all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "requested_at": r.requested_at,
        }
        for r in rows
    ]


@router.post("/password_requests/{rid}/approve")
async def approve_pwd(rid: int, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    r = await db.get(PasswordChangeRequest, rid)
    if not r or r.status != "pending":
        raise HTTPException(404, "Not found")
    u = await db.get(User, r.user_id)
    if not u:
        raise HTTPException(404, "User not found")
    u.password_hash = r.new_hash
    r.status = "approved"
    r.processed_at = datetime.utcnow()
    r.processed_by = admin.id
    await db.commit()
    return {"ok": True}


@router.post("/password_requests/{rid}/reject")
async def reject_pwd(rid: int, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    r = await db.get(PasswordChangeRequest, rid)
    if not r or r.status != "pending":
        raise HTTPException(404, "Not found")
    r.status = "rejected"
    r.processed_at = datetime.utcnow()
    r.processed_by = admin.id
    await db.commit()
    return {"ok": True}


@router.post("/macro/generate")
async def generate_macro(db: AsyncSession = Depends(get_db), user=Depends(require_admin), slot: str | None = None):
    # Hormati toggle LLM dan budget; beri pesan ramah jika OFF
    s = await get_or_init_settings(db)
    allowed, reason = await services.llm.should_use_llm(db)
    if not allowed:
        # 409 agar FE bisa tampilkan pesan tanpa 500
        raise HTTPException(409, detail=(
            "LLM sedang nonaktif: " + (reason or "dinonaktifkan oleh admin/budget.")
        ))
    # Pastikan API key tersedia
    if not os.getenv("OPENAI_API_KEY") and getattr(app_settings, "APP_ENV", "local") != "local":
        raise HTTPException(409, detail="LLM belum dikonfigurasi: OPENAI_API_KEY belum diisi.")

    # Prompt: prefer JSON but accept plain text for backward-compat
    prompt = (
        "Balas dalam JSON dengan kunci: {date_utc (opsional), summary, "
        "sections:[{title,bullets:[]}], sources}. Bahasa Indonesia, netral, ringkas. "
        "Cakup 24-48 jam: DXY, yield riil, likuiditas kripto, ETF/flow, berita utama."
    )

    try:
        text, usage = services.llm.ask_llm(prompt)
        # Catat biaya penggunaan ke budget tracking
        await add_usage(
            db,
            user.id,
            os.getenv("OPENAI_MODEL", "gpt-5-chat-latest"),
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            s.input_usd_per_1k,
            s.output_usd_per_1k,
        )
        # Jika melewati limit, auto-off
        await check_budget_and_maybe_off(db)
    except Exception as e:  # pragma: no cover
        msg = str(e).lower()
        # Kunci API tidak valid / unauthorized → berikan pesan yang jelas
        if "401" in msg or "unauthorized" in msg or "invalid api key" in msg or "authentication" in msg:
            raise HTTPException(409, detail=(
                "LLM belum dikonfigurasi dengan benar: OPENAI_API_KEY tidak valid atau tidak berizin."
            ))
        # Model tidak mendukung JSON strict response_format
        if "response_format" in msg and ("unsupported" in msg or "not supported" in msg):
            raise HTTPException(409, detail=(
                "Model LLM tidak mendukung JSON strict. Set OPENAI_JSON_STRICT=0 atau ganti model."
            ))
        # Model tidak ditemukan
        if "model" in msg and "not found" in msg:
            raise HTTPException(409, detail=(
                "Model LLM tidak ditemukan. Periksa OPENAI_MODEL dan izin akses model."
            ))
        # Timeout / koneksi
        if "timeout" in msg or "timed out" in msg:
            raise HTTPException(504, detail=(
                "Timeout mengakses LLM. Coba lagi atau naikkan LLM_TIMEOUT_S."
            ))
        if "connection" in msg or "dns" in msg or "ssl" in msg:
            raise HTTPException(502, detail=(
                "Gagal koneksi ke LLM (jaringan/DNS/SSL). Periksa koneksi server."
            ))
        if "insufficient_quota" in msg or " 429" in msg or "rate limit" in msg:
            s.use_llm = False
            await db.commit()
            raise HTTPException(
                503,
                detail=(
                    "LLM dinonaktifkan sementara: kuota habis atau rate limit. "
                    "Silakan tambah kredit/limit lalu aktifkan kembali di halaman Admin."
                ),
            )
        # Error lain: tampilkan pesan generik agar tidak bocor detail
        raise HTTPException(502, detail="Gagal mengakses LLM. Coba lagi nanti.")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Try parse structured JSON; fallback to narrative text
    narrative = text
    sources: str | list | None = ""
    sections: list | dict | str | None = []
    try:
        import json as _json
        parsed = _json.loads(text)
        narrative = parsed.get("summary") or parsed.get("narrative") or narrative
        sections = parsed.get("sections") or []
        sources = parsed.get("sources") or ""
        # Normalize sections into list
        if isinstance(sections, str):
            try:
                sections = _json.loads(sections)
            except Exception:
                sections = []
        if isinstance(sections, dict):
            sections = [sections]
    except Exception:
        pass
    # Upsert per slot (pagi/malam) idempotent
    try:
        from zoneinfo import ZoneInfo
        jkt = ZoneInfo("Asia/Jakarta")
        now_wib = datetime.now(timezone.utc).astimezone(jkt)
        slot_val = (slot or ("pagi" if now_wib.hour < 12 else "malam")).lower()
    except Exception:
        slot_val = (slot or "pagi").lower()
    qslot = await db.execute(select(MacroDaily).where(MacroDaily.date_utc == today, MacroDaily.slot == slot_val))
    row_slot = qslot.scalar_one_or_none()
    # Coerce sources to text
    def _src_to_text(src):
        if isinstance(src, list):
            try:
                return "\n".join(map(str, src))
            except Exception:
                return "\n".join([str(x) for x in src])
        return str(src or "")

    if row_slot:
        row_slot.narrative = narrative
        row_slot.sources = _src_to_text(sources)
        try:
            row_slot.sections = sections if isinstance(sections, list) else []
            row_slot.last_run_status = "ok"
        except Exception:
            pass
    else:
        row_slot = MacroDaily(date_utc=today, slot=slot_val, narrative=narrative, sources=_src_to_text(sources))
        try:
            row_slot.sections = sections if isinstance(sections, list) else []
            row_slot.last_run_status = "ok"
        except Exception:
            pass
        db.add(row_slot)
    await db.commit()
    return {"ok": True, "date": today, "slot": slot_val}


@router.get("/macro/status")
async def macro_status(db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    from sqlalchemy import desc
    q = await db.execute(select(MacroDaily).order_by(desc(MacroDaily.created_at)).limit(1))
    row = q.scalar_one_or_none()
    if not row:
        return {"has_data": False}
    return {
        "has_data": True,
        "date_utc": row.date_utc,
        "created_at": row.created_at,
        "slot": getattr(row, "slot", None),
        "last_run_status": getattr(row, "last_run_status", None),
    }


@router.get("/futures/signals")
async def futures_signals(symbol: str = "BTCUSDT", db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    return await futures_svc.latest_signals(db, symbol)


@router.post("/futures/refresh")
async def futures_refresh(symbol: str = "BTCUSDT", db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    row = await futures_svc.refresh_signals_cache(db, symbol)
    return {"ok": True, "symbol": row.symbol, "created_at": row.created_at}
@router.post("/parity/compute")
async def parity_compute(payload: dict, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    """Hitung paritas indikator terhadap referensi.
    payload: { ohlcv: [{ts,open,high,low,close,volume},...], expected: {fvg:[], zones:[]},
               tol_price?: float, tol_idx?: int, min_iou?: float,
               fvg_use_bodies?: bool, fvg_fill_rule?: str,
               sd_max_base?: int, sd_body_ratio?: float, sd_min_departure?: float }
    """
    rows = payload.get("ohlcv") or []
    if not rows:
        raise HTTPException(422, "ohlcv kosong")
    df = pd.DataFrame(rows)
    df = df[["ts","open","high","low","close","volume"]]
    exp = payload.get("expected") or {}
    tol_price = float(payload.get("tol_price", 1e-4))
    tol_idx = int(payload.get("tol_idx", 1))
    min_iou = float(payload.get("min_iou", 0.6))

    # gunakan setting payload override atau dari DB
    s = await get_or_init_settings(db)
    fvg_use_bodies = bool(payload.get("fvg_use_bodies", getattr(s, "fvg_use_bodies", False)))
    fvg_fill_rule = str(payload.get("fvg_fill_rule", getattr(s, "fvg_fill_rule", "any_touch")))
    sd_max_base = int(payload.get("sd_max_base", getattr(s, "sd_max_base", 3)))
    sd_body_ratio = float(payload.get("sd_body_ratio", getattr(s, "sd_body_ratio", 0.33)))
    sd_min_departure = float(payload.get("sd_min_departure", getattr(s, "sd_min_departure", 1.5)))

    # jalankan deteksi
    fvg_got = services.fvg.detect_fvg(df, use_bodies=fvg_use_bodies, fill_rule=fvg_fill_rule)
    zones_got = services.supply_demand.detect_zones(df, max_base=sd_max_base, body_ratio=sd_body_ratio, min_departure=sd_min_departure)
    # hitung skor
    fvg_stats = fvg_parity_stats(exp.get("fvg", []), fvg_got, tol_price=tol_price, tol_idx=tol_idx)
    z_stats = zones_parity_stats(exp.get("zones", []), zones_got, tol_idx=tol_idx, min_iou=min_iou)
    return {"fvg": fvg_stats, "zones": z_stats, "counts": {"fvg_ref": len(exp.get("fvg", [])), "fvg_got": len(fvg_got), "zones_ref": len(exp.get("zones", [])), "zones_got": len(zones_got)}}

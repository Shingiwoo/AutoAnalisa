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
        # new aliases
        "llm_enabled": s.use_llm,
        "llm_model": llm_model,
        "llm_limit_monthly_usd": s.budget_monthly_usd,
        "llm_spend_monthly_usd": s.budget_used_usd,
    }


def _apply_settings_payload(s, payload: dict):
    # Support both legacy and new keys
    mapping = {
        "use_llm": "use_llm",
        "registration_enabled": "registration_enabled",
        "budget_monthly_usd": "budget_monthly_usd",
        "auto_off_at_budget": "auto_off_at_budget",
        "input_usd_per_1k": "input_usd_per_1k",
        "output_usd_per_1k": "output_usd_per_1k",
        # new aliases
        "llm_enabled": "use_llm",
        "llm_limit_monthly_usd": "budget_monthly_usd",
    }
    bool_fields = {"use_llm", "registration_enabled", "auto_off_at_budget"}
    float_fields = {"budget_monthly_usd", "input_usd_per_1k", "output_usd_per_1k"}
    for k, attr in mapping.items():
        if k in payload:
            v = payload[k]
            try:
                if attr in bool_fields:
                    v = bool(v)
                elif attr in float_fields:
                    v = float(v)
                    # guardrails: negative values don't make sense
                    if attr == "budget_monthly_usd" and v < 0:
                        v = 0.0
                    if attr in {"input_usd_per_1k", "output_usd_per_1k"} and v < 0:
                        v = 0.0
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
            "budget_monthly_usd": s.budget_monthly_usd,
            "auto_off_at_budget": s.auto_off_at_budget,
            "input_usd_per_1k": s.input_usd_per_1k,
            "output_usd_per_1k": s.output_usd_per_1k,
            "budget_used_usd": s.budget_used_usd,
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
async def generate_macro(db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
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

    # Prompt sederhana; bisa dikembangkan untuk ambil feed publik lebih dahulu
    prompt = (
        "Ringkas faktor makro relevan untuk pasar kripto 24-48 jam ke depan. "
        "Singgung DXY, yield, likuiditas, sentimen ETF, berita utama. "
        "Bahasa Indonesia, 5-8 poin, netral, tidak memberi rekomendasi investasi."
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
    q = await db.execute(select(MacroDaily).where(MacroDaily.date_utc == today))
    row = q.scalar_one_or_none()
    if row:
        row.narrative = text
    else:
        row = MacroDaily(date_utc=today, narrative=text, sources="")
        db.add(row)
    await db.commit()
    return {"ok": True, "date": today}

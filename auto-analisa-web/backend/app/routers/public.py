from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_db
from app.services.budget import get_or_init_settings
from app.models import Notification


router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/settings")
async def public_settings(db: AsyncSession = Depends(get_db)):
    s = await get_or_init_settings(db)
    return {
        "show_sessions_hint": getattr(s, "show_sessions_hint", True),
        "default_weight_profile": getattr(s, "default_weight_profile", "DCA"),
        "futures_funding_alert_enabled": getattr(s, "futures_funding_alert_enabled", True),
        "futures_funding_alert_window_min": getattr(s, "futures_funding_alert_window_min", 30),
    }


@router.post("/notify_admin")
async def notify_admin(payload: dict, db: AsyncSession = Depends(get_db)):
    # Lightweight notification creator (rate-limit can be added if needed)
    kind = str(payload.get("kind") or "info")
    title = str(payload.get("title") or "Notifikasi")
    body = str(payload.get("body") or "")
    try:
        n = Notification(kind=kind, title=title, body=body, status="unread", meta=payload.get("meta") or {})
        db.add(n)
        await db.commit()
        return {"ok": True}
    except Exception:
        raise HTTPException(500, "Gagal membuat notifikasi")

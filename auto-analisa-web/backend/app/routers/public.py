from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_db
from app.services.budget import get_or_init_settings


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

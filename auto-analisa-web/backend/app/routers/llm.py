from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.auth import require_user
from app.services.llm import should_use_llm
from app.services.usage import get_today_usage
from app.services.budget import get_or_init_settings


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

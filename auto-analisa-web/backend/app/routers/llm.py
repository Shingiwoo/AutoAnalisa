from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.auth import require_user
from app.services.llm import should_use_llm
from app.services.usage import get_today_usage


router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/quota")
async def quota(db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    usage = await get_today_usage(db, user_id=user.id)
    allowed, _ = await should_use_llm(db)
    llm_enabled = bool(allowed) and usage["remaining"] > 0
    return {
        "limit": usage["limit"],
        "remaining": usage["remaining"],
        "calls": usage["calls"],
        "llm_enabled": llm_enabled,
    }


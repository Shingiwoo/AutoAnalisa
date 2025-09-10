from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.deps import get_db
from app.routers.auth import get_user_from_auth
from app.models import Settings, ApiUsage
from app.services.budget import get_or_init_settings, month_key


router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user=Depends(get_user_from_auth)):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    s = await get_or_init_settings(db)
    return {
        "use_llm": s.use_llm,
        "budget_monthly_usd": s.budget_monthly_usd,
        "auto_off_at_budget": s.auto_off_at_budget,
        "budget_used_usd": s.budget_used_usd,
        "input_usd_per_1k": s.input_usd_per_1k,
        "output_usd_per_1k": s.output_usd_per_1k,
        "month_key": month_key(),
    }


@router.post("/settings")
async def update_settings(payload: dict, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    s = await get_or_init_settings(db)
    for k in [
        "use_llm",
        "budget_monthly_usd",
        "auto_off_at_budget",
        "input_usd_per_1k",
        "output_usd_per_1k",
    ]:
        if k in payload:
            setattr(s, k, payload[k])
    await db.commit()
    return {"ok": True}


@router.get("/usage")
async def usage(db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    mk = month_key()
    q = await db.execute(select(ApiUsage).where(ApiUsage.month_key == mk))
    rows = q.scalars().all()
    total = sum(r.usd_cost for r in rows)
    return {"month_key": mk, "count": len(rows), "total_usd": total}


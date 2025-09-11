from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.deps import get_db
from app.models import MacroDaily
from datetime import datetime, timezone

router = APIRouter(prefix="/api/macro", tags=["macro"])


@router.get("/today")
async def today(db: AsyncSession = Depends(get_db)):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    q = await db.execute(select(MacroDaily).where(MacroDaily.date_utc == today))
    row = q.scalar_one_or_none()
    if not row:
        # fallback latest available
        q2 = await db.execute(select(MacroDaily).order_by(desc(MacroDaily.created_at)))
        row = q2.scalar_one_or_none()
        if not row:
            return {"date": today, "narrative": "", "sources": ""}
    return {"date": row.date_utc, "narrative": row.narrative, "sources": row.sources}


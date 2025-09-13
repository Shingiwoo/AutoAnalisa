from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.deps import get_db
from app.models import MacroDaily
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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
    # Also provide date_wib for UI convenience
    try:
        jkt = ZoneInfo("Asia/Jakarta")
        dt_utc = datetime.fromisoformat(row.date_utc).replace(tzinfo=timezone.utc)
        date_wib = dt_utc.astimezone(jkt).date().isoformat()
    except Exception:
        date_wib = row.date_utc
    return {"date": row.date_utc, "date_wib": date_wib, "narrative": row.narrative, "sources": row.sources, "sections": getattr(row, "sections", [])}

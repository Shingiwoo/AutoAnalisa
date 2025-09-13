from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_db
from app.services.sessions import btc_wib_buckets


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/btc/wib")
async def btc_wib(tf: str = "1h", days: int = 120, db: AsyncSession = Depends(get_db)):
    # db kept for possible caching later
    buckets = await btc_wib_buckets(days=days, timeframe=tf)
    return buckets


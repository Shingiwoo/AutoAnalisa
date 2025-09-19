
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_db
from app.services.market import fetch_bundle
from app.services.rules import Features
from app.services.futures import latest_signals
from app.services.strategy_futures import build_plan_futures

router = APIRouter(prefix="/futures", tags=["futures"])

@router.get("/plan/{symbol}")
async def build_plan(symbol: str, db: AsyncSession = Depends(get_db)):
    bundle = await fetch_bundle(symbol, tfs=("4h","1h","15m","5m"), market="futures")
    feat = Features(bundle); feat.enrich()
    sig = await latest_signals(db, symbol)
    plan = build_plan_futures(bundle, feat, side_hint="AUTO", fut_signals=sig, symbol=symbol)
    return {"ok": True, "symbol": symbol.upper(), "plan": plan, "signals": sig}

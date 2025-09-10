from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import AnalyzeIn
from .storage.db import init_db
from .storage import repo
from .services.locks import LockService
from .config import settings
from .deps import get_db

try:
    from redis.asyncio import Redis

    rcli = Redis.from_url(settings.REDIS_URL)
except Exception:  # pragma: no cover
    rcli = None

app = FastAPI(title="Auto Analisa Web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
locks = LockService(rcli)


@app.on_event("startup")
async def _startup():
    await init_db()


@app.get("/api/health")
async def health():
    return {"ok": True}


from .workers.analyze_worker import run_analyze


@app.post("/api/analyze")
async def analyze(data: AnalyzeIn, db: AsyncSession = Depends(get_db)):
    user_id = "user-local"  # lokal: stub; FE bisa kirim header nanti
    key = f"{user_id}:{data.symbol}"
    if not await locks.acquire(key, ttl=20):
        raise HTTPException(status_code=429, detail="Job sedang berjalan untuk simbol ini.")
    try:
        plan = await run_analyze(data.symbol, data.options.dict())
        saved = await repo.save_plan(db, user_id, data.symbol, plan)
        return {
            "id": saved.id,
            "user_id": saved.user_id,
            "symbol": saved.symbol,
            "version": saved.version,
            "payload": plan,
            "created_at": str(saved.created_at),
        }
    finally:
        await locks.release(key)


@app.get("/api/plan/{plan_id}")
async def get_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    p = await repo.get_plan(db, plan_id)
    if not p:
        raise HTTPException(404)
    return {
        "id": p.id,
        "user_id": p.user_id,
        "symbol": p.symbol,
        "version": p.version,
        "payload": p.payload_json,
        "created_at": str(p.created_at),
    }


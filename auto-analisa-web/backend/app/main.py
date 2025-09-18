from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB, redis etc.
    await init_db()
    yield
    # Shutdown: nothing for now


app = FastAPI(title="Auto Analisa Web", lifespan=lifespan)
# CORS: jika APP_ENV != local dan origins di-set, gunakan; selain itu izinkan semua (dev)
cors_origins = ["*"]
try:
    if settings.APP_ENV != "local" and settings.CORS_ORIGINS and settings.CORS_ORIGINS.strip() != "*":
        cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
except Exception:
    pass
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
locks = LockService(rcli)


@app.get("/api/health")
async def health():
    return {"ok": True}


from .routers import auth as auth_router
from .routers import analyze as analyze_router
from .routers import admin as admin_router
from .routers import analyses as analyses_router
from .routers import watchlist as watchlist_router
from .routers import market as market_router
from .routers import macro as macro_router
from .routers import user as user_router
from .routers import llm as llm_router
from .routers import sessions as sessions_router
from .routers import public as public_router
from .routers import futures as futures_router
from .routers import meta as meta_router


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

# Include new routers
app.include_router(auth_router.router)
app.include_router(analyze_router.router)
app.include_router(admin_router.router)
app.include_router(analyses_router.router)
app.include_router(watchlist_router.router)
app.include_router(market_router.router)
app.include_router(macro_router.router)
app.include_router(user_router.router)
app.include_router(llm_router.router)
app.include_router(sessions_router.router)
app.include_router(public_router.router)
app.include_router(futures_router.router)
app.include_router(meta_router.router)

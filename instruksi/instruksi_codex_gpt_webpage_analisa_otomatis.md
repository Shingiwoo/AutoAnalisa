# Instruksi untuk Codex GPT (VS Code) — Webpage Analisa Otomatis (Localserver)
Dokumen ini adalah **skrip instruksi** yang bisa kamu _copy‑paste_ ke Codex GPT (VS Code) agar menghasilkan proyek baru **webpage analisa otomatis** tanpa screenshot. Arsitektur: **Next.js (FE) + FastAPI (BE) + Redis (lock & queue) + SQLite**. Target: Test runing berjalan di **localserver** untuk **1–4 user** tanpa tabrakan.

---

## 0) Prasyarat Lokal
- Node.js ≥ 20, npm ≥ 10  
- Python ≥ 3.11, pip  
- Docker
- Redis
- Git

---

## 1) Perintah Utama ke Codex GPT
> Kirimkan blok ini **apa adanya** ke Codex GPT di VS Code.

```
TOLONG BUATKAN PROYEK BARU bernama `auto-analisa-web` dengan struktur FE+BE berikut dan jalankan di localserver.

### A. Struktur Folder
auto-analisa-web/
  README.md
  docker-compose.yml
  .env.example
  backend/
    app/
      __init__.py
      main.py
      config.py
      models.py
      schemas.py
      deps.py
      services/
        market.py
        indicators.py
        rules.py
        planner.py
        gating.py
        locks.py
      storage/
        db.py
        repo.py
      workers/
        analyze_worker.py
      tests/
        test_api_basic.py
    requirements.txt
    pyproject.toml
  frontend/
    package.json
    next.config.js
    tailwind.config.js
    postcss.config.js
    src/
      app/
        layout.tsx
        page.tsx
        api.ts
        (components)/
          AnalyzeForm.tsx
          PlanCard.tsx
          VersionList.tsx
          Loader.tsx
      styles/globals.css

### B. File Konten — BUATKAN KODE LENGKAP
1) docker-compose.yml (untuk Redis saja):
-------------------------------------------------
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --appendonly yes
-------------------------------------------------

2) .env.example (root):
-------------------------------------------------
# BACKEND
APP_ENV=local
SECRET_KEY=dev-secret
SQLITE_URL=sqlite+aiosqlite:///./app.db
REDIS_URL=redis://localhost:6379/0
BINANCE_SANDBOX=false
USE_LLM=false
# FRONTEND
NEXT_PUBLIC_API_BASE=http://localhost:8000
-------------------------------------------------

3) backend/requirements.txt:
-------------------------------------------------
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
pydantic-settings==2.5.2
sqlalchemy[asyncio]==2.0.35
aiosqlite==0.20.0
redis==5.0.8
ccxt==4.5.3
numpy==1.26.4
python-multipart==0.0.9
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.23.8
-------------------------------------------------

4) backend/pyproject.toml (opsional, untuk ruff/black jika ada):
-------------------------------------------------
[tool.black]
line-length = 100
skip-string-normalization = true

[tool.ruff]
line-length = 100
-------------------------------------------------

5) backend/app/config.py:
-------------------------------------------------
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "local"
    SECRET_KEY: str
    SQLITE_URL: str
    REDIS_URL: str
    BINANCE_SANDBOX: bool = False
    USE_LLM: bool = False

settings = Settings()
-------------------------------------------------

6) backend/app/models.py (SQLAlchemy — tabel plans & users minimal):
-------------------------------------------------
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, JSON
import datetime as dt

Base = declarative_base()

class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
-------------------------------------------------

7) backend/app/schemas.py (Pydantic):
-------------------------------------------------
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict, Any

class AnalyzeOptions(BaseModel):
    tf: Tuple[str, str, str] = ("4h","1h","15m")
    risk_pct: float = 0.008
    mode: str = "auto"  # auto|PB|BO

class PlanPayload(BaseModel):
    bias: str
    support: List[Any]
    resistance: List[Any]
    mode: str
    entries: List[float]
    weights: List[float]
    invalid: float
    tp: List[float]
    score: int
    narrative: str

class PlanOut(BaseModel):
    id: int
    user_id: str
    symbol: str
    version: int
    payload: PlanPayload
    created_at: str

class AnalyzeIn(BaseModel):
    symbol: str
    options: AnalyzeOptions = AnalyzeOptions()
-------------------------------------------------

8) backend/app/storage/db.py (Async engine & session):
-------------------------------------------------
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from . import models
from ..config import settings

engine = create_async_engine(settings.SQLITE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
-------------------------------------------------

9) backend/app/services/locks.py (Redis lock, fallback in-memory):
-------------------------------------------------
import asyncio
import time
from typing import Optional

try:
    import redis
    from redis.asyncio import Redis
except Exception:
    Redis = None

class LockService:
    def __init__(self, redis_client: Optional["Redis"], namespace: str = "lock"):
        self.r = redis_client
        self.ns = namespace
        self.local = {}

    async def acquire(self, key: str, ttl: int = 30) -> bool:
        namespaced = f"{self.ns}:{key}"
        if self.r:
            return await self.r.set(namespaced, "1", ex=ttl, nx=True) is True
        # fallback local
        now = time.time()
        if namespaced in self.local and self.local[namespaced] > now:
            return False
        self.local[namespaced] = now + ttl
        return True

    async def release(self, key: str):
        namespaced = f"{self.ns}:{key}"
        if self.r:
            await self.r.delete(namespaced)
        else:
            self.local.pop(namespaced, None)
-------------------------------------------------

10) backend/app/services/market.py (ccxt fetch klines + helpers):
-------------------------------------------------
import ccxt
import pandas as pd
from typing import Dict

ex = ccxt.binance()

async def fetch_klines(symbol: str, timeframe: str, limit: int = 500):
    # ccxt sync, bungkus async tipis — untuk local OK
    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    import pandas as pd
    df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
    return df

async def fetch_bundle(symbol: str, tfs=("4h","1h","15m")) -> Dict[str, "pd.DataFrame"]:
    out = {}
    for tf in tfs:
        out[tf] = await fetch_klines(symbol, tf, 300 if tf=="15m" else 600)
    return out
-------------------------------------------------

11) backend/app/services/indicators.py (EMA/BB/RSI/MACD/ATR/MA‑vol):
-------------------------------------------------
import numpy as np
import pandas as pd

def ema(series: pd.Series, n: int):
    return series.ewm(span=n, adjust=False).mean()

def bb(series: pd.Series, n=20, k=2.0):
    mb = series.rolling(n).mean()
    sd = series.rolling(n).std(ddof=0)
    ub, dn = mb + k*sd, mb - k*sd
    return mb, ub, dn

def rsi(series: pd.Series, n=14):
    delta = series.diff()
    gain = np.where(delta>0, delta, 0.0)
    loss = np.where(delta<0, -delta, 0.0)
    roll_up = pd.Series(gain).rolling(n).mean()
    roll_down = pd.Series(loss).rolling(n).mean()
    rs = roll_up / (roll_down + 1e-9)
    rsi = 100 - (100/(1+rs))
    return pd.Series(rsi, index=series.index)

def macd(series: pd.Series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

def atr(df: pd.DataFrame, n=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()
-------------------------------------------------

12) backend/app/services/rules.py (skoring & level):
-------------------------------------------------
from .indicators import ema, bb, rsi, macd, atr
import numpy as np

class Features:
    def __init__(self, bundle):
        self.b = bundle  # dict tf->df

    def enrich(self):
        for tf, df in self.b.items():
            df["ema5"] = ema(df.close,5)
            df["ema20"] = ema(df.close,20)
            df["ema50"] = ema(df.close,50)
            df["ema100"] = ema(df.close,100)
            df["ema200"] = ema(df.close,200)
            df["mb"], df["ub"], df["dn"] = bb(df.close)
            df["rsi14"] = rsi(df.close,14)
            m,s,h = macd(df.close)
            df["macd"], df["signal"], df["hist"] = m,s,h
            df["atr14"] = atr(df,14)
        return self.b

    def latest(self, tf):
        return self.b[tf].iloc[-1]


def score_symbol(feat: Features):
    f4, f1, f15 = feat.latest('4h'), feat.latest('1h'), feat.latest('15m')
    ts = sum([
        f15.ema5>f15.ema20>f15.ema50>f15.ema100>f15.ema200,
        f1.ema5>f1.ema20>f1.ema50>f1.ema100>f1.ema200,
    ]) * 5  # 0,5,10
    loc = 0
    loc += 5 if f1.close > f1.mb else 0
    loc += 5 if f4.close < f4.ub else 0
    mom = 5 if 55 <= f1.rsi14 <= 68 else (3 if 50<=f1.rsi14<55 else 1)
    vol = 5  # placeholder; bisa pakai MA-volume
    cl = 5   # placeholder: akan naik bila RR ok
    return int(ts+loc+mom+vol+cl)


def make_levels(feat: Features):
    f1, f15, f4 = feat.latest('1h'), feat.latest('15m'), feat.latest('4h')
    support1 = round(float(max(min(f15.mb, f15.ema20), min(f1.mb, f1.ema20))), 6)
    support2 = round(float(min(f15.ema50, f1.ema50)), 6)
    res1 = round(float(max(f1.ub, f1.high)), 6)
    res2 = round(float(max(f4.ub, f4.high)), 6)
    return {
        'support': [support1, support2],
        'resistance': [res1, res2]
    }
-------------------------------------------------

13) backend/app/services/planner.py (PB/BO + TP/Invalid):
-------------------------------------------------
from .rules import make_levels

def build_plan(bundle, feat, score, mode="auto"):
    lv = make_levels(feat)
    s1, s2 = lv['support']
    r1, r2 = lv['resistance']
    price = float(bundle['15m'].iloc[-1].close)
    pb1, pb2 = max(s1, price*0.995), max(s2, price*0.99)
    invalid = min(s2, pb2*0.995)
    tp1, tp2 = r1, r2
    if mode == 'BO' or (mode=='auto' and price>r1*0.995):
        trig = round(r1*1.001,6); lim = round(trig*1.0005,6)
        entries = [trig,]
        weights = [1.0]
    else:
        entries = [round(pb1,6), round(pb2,6)]
        weights = [0.6,0.4]
    bias = "Bullish intraday selama struktur 1H bertahan di atas %.4f–%.4f."%(s1,s2)
    narrative = f"TP1 {tp1:.4f}, TP2 {tp2:.4f}, invalid {invalid:.4f}. Score {score}."
    return {
        'bias': bias,
        'support': [s1, s2],
        'resistance': [r1, r2],
        'mode': mode if mode!='auto' else 'PB',
        'entries': entries,
        'weights': weights,
        'invalid': round(invalid,6),
        'tp': [round(tp1,6), round(tp2,6)],
        'score': score,
        'narrative': narrative
    }
-------------------------------------------------

14) backend/app/services/gating.py (BTC gate sederhana):
-------------------------------------------------
async def btc_gate_ok():
    # stub: selalu OK di local; bisa diperluas ambil BTCUSDT 15m
    return True
-------------------------------------------------

15) backend/app/deps.py (dep redis & db session):
-------------------------------------------------
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .storage.db import SessionLocal

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
-------------------------------------------------

16) backend/app/services/__init__.py (kosong atau eksport):
-------------------------------------------------
# marker package
-------------------------------------------------

17) backend/app/storage/repo.py (simpan versi Plan):
-------------------------------------------------
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..models import Plan

async def save_plan(db: AsyncSession, user_id: str, symbol: str, payload: dict) -> Plan:
    q = await db.execute(select(func.max(Plan.version)).where(Plan.user_id==user_id, Plan.symbol==symbol))
    ver = (q.scalar() or 0) + 1
    p = Plan(user_id=user_id, symbol=symbol, version=ver, payload_json=payload)
    db.add(p)
    await db.commit(); await db.refresh(p)
    return p

async def get_plan(db: AsyncSession, plan_id: int) -> Plan | None:
    return await db.get(Plan, plan_id)
-------------------------------------------------

18) backend/app/workers/analyze_worker.py (job analisa):
-------------------------------------------------
from .services.market import fetch_bundle
from .services.rules import Features, score_symbol
from .services.planner import build_plan

async def run_analyze(symbol: str, options: dict):
    bundle = await fetch_bundle(symbol, tuple(options.get('tf',["4h","1h","15m"])) )
    feat = Features(bundle).enrich() or Features(bundle)
    score = score_symbol(Features(bundle))
    plan = build_plan(bundle, Features(bundle), score, options.get('mode','auto'))
    return plan
-------------------------------------------------

19) backend/app/main.py (FastAPI endpoints):
-------------------------------------------------
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import AnalyzeIn, PlanOut, PlanPayload
from .storage.db import init_db
from .storage import repo
from .services.locks import LockService
from ..app.config import settings

try:
    from redis.asyncio import Redis
    rcli = Redis.from_url(settings.REDIS_URL)
except Exception:
    rcli = None

app = FastAPI(title="Auto Analisa Web")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
locks = LockService(rcli)

@app.on_event("startup")
async def _startup():
    await init_db()

@app.get("/api/health")
async def health():
    return {"ok": True}

from .workers.analyze_worker import run_analyze

@app.post("/api/analyze")
async def analyze(data: AnalyzeIn, db: AsyncSession = Depends(lambda: __import__('..').app.deps.get_db())):
    user_id = "user-local"  # lokal: stub; FE akan kirim header nanti
    key = f"{user_id}:{data.symbol}"
    if not await locks.acquire(key, ttl=20):
        raise HTTPException(status_code=429, detail="Job sedang berjalan untuk simbol ini.")
    try:
        plan = await run_analyze(data.symbol, data.options.dict())
        saved = await repo.save_plan(db, user_id, data.symbol, plan)
        return {"id": saved.id, "user_id": saved.user_id, "symbol": saved.symbol, "version": saved.version, "payload": plan, "created_at": str(saved.created_at)}
    finally:
        await locks.release(key)

@app.get("/api/plan/{plan_id}")
async def get_plan(plan_id: int, db: AsyncSession = Depends(lambda: __import__('..').app.deps.get_db())):
    p = await repo.get_plan(db, plan_id)
    if not p:
        raise HTTPException(404)
    return {"id": p.id, "user_id": p.user_id, "symbol": p.symbol, "version": p.version, "payload": p.payload_json, "created_at": str(p.created_at)}
-------------------------------------------------

20) frontend/package.json (Next.js + Tailwind):
-------------------------------------------------
{
  "name": "frontend",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000"
  },
  "dependencies": {
    "next": "14.2.9",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "zustand": "4.5.2",
    "clsx": "2.1.1",
    "axios": "1.7.7"
  },
  "devDependencies": {
    "autoprefixer": "10.4.20",
    "postcss": "8.4.47",
    "tailwindcss": "3.4.10",
    "typescript": "5.5.4"
  }
}
-------------------------------------------------

21) frontend/tailwind.config.js & postcss.config.js & next.config.js standar.

22) frontend/src/app/api.ts (helper axios):
-------------------------------------------------
import axios from 'axios'
export const api = axios.create({ baseURL: process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000' })
-------------------------------------------------

23) frontend/src/app/layout.tsx (basic):
-------------------------------------------------
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id"><body className="min-h-screen bg-zinc-50 text-zinc-900">{children}</body></html>
  )
}
-------------------------------------------------

24) frontend/src/app/(components)/AnalyzeForm.tsx:
-------------------------------------------------
'use client'
import {useState} from 'react'
import {api} from '../api'

export default function AnalyzeForm({onDone}:{onDone:(plan:any)=>void}){
  const [symbol,setSymbol]=useState('OPUSDT')
  const [loading,setLoading]=useState(false)
  async function submit(){
    setLoading(true)
    try{ const {data}=await api.post('/api/analyze',{symbol}) ; onDone(data)} finally{ setLoading(false) }
  }
  return (
    <div className="p-4 rounded-2xl shadow bg-white flex gap-2 items-end">
      <div className="flex flex-col">
        <label className="text-sm">Symbol</label>
        <input className="border rounded px-3 py-2" value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())}/>
      </div>
      <button onClick={submit} disabled={loading} className="px-4 py-2 rounded bg-black text-white">{loading?'Analisa…':'Analisa'}</button>
    </div>
  )
}
-------------------------------------------------

25) frontend/src/app/(components)/PlanCard.tsx:
-------------------------------------------------
'use client'
export default function PlanCard({plan, onUpdate}:{plan:any,onUpdate:()=>void}){
  const p=plan.payload
  return (
    <div className="p-4 rounded-2xl shadow bg-white space-y-2">
      <div className="text-lg font-semibold">{plan.symbol} • v{plan.version} • Skor {p.score}</div>
      <div className="text-sm opacity-70">{new Date(plan.created_at).toLocaleString('id-ID')}</div>
      <div className="whitespace-pre-wrap text-sm">
        <b>Bias Dominan:</b> {p.bias}
        {'\n'}<b>Level Kunci</b>{'\n'}Support: {p.support.join(' · ')}{'\n'}Resistance: {p.resistance.join(' · ')}
        {'\n'}<b>Rencana Eksekusi (spot)</b>{'\n'}PB: {p.entries.join(' / ')} (w={p.weights.join('/')}) • Invalid: {p.invalid}
        {'\n'}TP: {p.tp.join(' → ')}
        {'\n'}<b>Bacaan Sinyal:</b> {p.narrative}
      </div>
      <button onClick={onUpdate} className="px-3 py-2 rounded bg-zinc-900 text-white">Update</button>
    </div>
  )
}
-------------------------------------------------

26) frontend/src/app/page.tsx:
-------------------------------------------------
'use client'
import {useState} from 'react'
import AnalyzeForm from './(components)/AnalyzeForm'
import PlanCard from './(components)/PlanCard'
import {api} from './api'

export default function Page(){
  const [plan,setPlan]=useState<any|null>(null)
  async function update(){ if(!plan) return; const {data}=await api.post('/api/analyze',{symbol:plan.symbol}); setPlan(data) }
  return (
    <main className="max-w-3xl mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-bold">Webpage Analisa Otomatis (Local)</h1>
      <AnalyzeForm onDone={setPlan} />
      {plan && <PlanCard plan={plan} onUpdate={update} />}
      <div className="text-xs opacity-60">Aturan: Edukasi, bukan saran finansial. Rate-limit aktif. Hasil per user terpisah.</div>
    </main>
  )
}
-------------------------------------------------

27) frontend/styles/globals.css: tailwind base/components/utilities.

### C. README.md — instruksi jalan lokal
Tuliskan langkah:
- `cp .env.example .env` (root)
- `docker compose up -d redis`
- Backend: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm install && npm run dev`
- Buka `http://localhost:3000`.

### D. TEST Minimal (pytest)
backend/app/tests/test_api_basic.py: tes `/api/health` dan `/api/analyze` (mock fetch_klines bila perlu).

### E. Kriteria Selesai
- FE menampilkan form pilih simbol, hasil analisa, tombol Update.  
- BE menyimpan versi ke SQLite, lock mencegah tabrakan, endpoint berjalan.  
- Proyek bisa jalan lokal dengan perintah di README.

```

### Setelah selesai
- Jalankan perintah yang ditulis di README.  
- Verifikasi alur: Analisa XRPUSDT → tampil hasil → klik **Update** → versi baru tampil.

---

## 2) Catatan untuk Codex (Penyesuaian Otomatis)
- Jika Redis tidak tersedia, **locks.py** sudah punya fallback in‑memory.  
- ccxt bersifat sinkron; pada local dipanggil dalam fungsi async, **boleh**. Untuk produksi bisa dialihkan ke worker _thread_.  
- Semua angka level dibulatkan `round(x, 6)`.  
- Rate‑limit sederhana: backend lock TTL 20 dtk sudah cukup untuk 1–4 user.

---

## 3) Validasi Manual (Checklist)
- `/api/health` mengembalikan `{ok:true}`.  
- Analisa pertama untuk `OPUSDT` sukses dan membuat `plans` v1.  
- Klik **Update** membuat v2 (timestamp berbeda).  
- Form dan hasil tampil rapi; narasi sesuai Format Analisa SPOT.

---

## 4) Lanjutan (Opsional)
- Auth tipis (token per user); kirim header `X-User-ID`.  
- History list per user + export JSON/PDF.  
- BTC gate nyata (ambil BTCUSDT 15m dan cek EMA20).  
- Notifikasi Telegram saat TP1/TP2 kena.


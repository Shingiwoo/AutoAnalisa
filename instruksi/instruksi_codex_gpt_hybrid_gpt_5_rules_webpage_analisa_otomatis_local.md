# Instruksi Codex GPT — Hybrid (GPT‑5 + Rules)
_Target_: Menjadikan proyek **auto-analisa-web** (yang sudah dibuat sebelumnya) memakai **Hybrid**: perhitungan angka (level/TP/SL) oleh **rules engine**, narasi & koherensi oleh **LLM GPT‑5** via **Responses API (Structured Outputs)**. Berjalan **local server** dulu.

> Catatan: Semua angka level **tetap dari rules**, LLM hanya merangkum & memastikan format **Analisa SPOT I** (maks 2 TP & TP 3 jika di aktifkan). Ada **fallback** ke rules-only jika LLM mati/timeout.

---

## 0) Prasyarat
- Proyek dasar **auto-analisa-web** sudah ada (FastAPI + Next.js + Redis + SQLite).  
- Python ≥ 3.11, Node ≥ 20.  
- Memiliki **OPENAI_API_KEY** aktif.

---

## 1) Patch: dependensi, env, dan struktur baru
> Kirim blok patch ini ke Codex GPT di VS Code (Terminal menyala di root repo). **Jalankan per bagian** (A → D) atau sekaligus.

```bash
# A) Tambah dependency backend
(cat <<'REQ' > backend/requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
pydantic-settings==2.5.2
sqlalchemy[asyncio]==2.0.35
aiosqlite==0.20.0
redis==5.0.8
ccxt==4.3.98
numpy==1.26.4
python-multipart==0.0.9
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.23.8
openai>=1.44.0
REQ
)

# B) Update .env.example (root)
awk '1; END{print "OPENAI_API_KEY=\nOPENAI_MODEL=gpt-5\nUSE_LLM=true\nLLM_TIMEOUT_S=20\nLLM_CACHE_TTL_S=300"}' .env.example > .env.example.tmp && mv .env.example.tmp .env.example

# C) Buat modul llm & schema
mkdir -p backend/app/services && cat > backend/app/services/llm.py <<'PY'
import os, json, hashlib, asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel
from openai import OpenAI

# Skema Analisa SPOT I (maks 2 TP)
ANALISA_SCHEMA = {
    "name": "spot_plan_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "bias": {"type": "string"},
            "support": {"type": "array", "items": {"type": ["number", "array"]}},
            "resistance": {"type": "array", "items": {"type": ["number", "array"]}},
            "plan": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "pullback": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "entries": {"type": "array", "items": {"type": "number"}},
                            "invalid": {"type": "number"},
                            "tp": {"type": "array", "items": {"type": "number"}}
                        },
                        "required": ["entries", "invalid", "tp"]
                    },
                    "breakout": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "trigger_limit": {"type": "array", "items": {"type": "number"}},
                            "retest_zone": {"type": ["array", "string"]},
                            "sl_fast": {"type": "number"},
                            "tp": {"type": "array", "items": {"type": "number"}}
                        },
                        "required": ["trigger_limit", "sl_fast", "tp"]
                    }
                },
                "required": ["pullback", "breakout"]
            },
            "signals": {"type": "string"},
            "fundamental": {"type": "string"}
        },
        "required": ["bias", "support", "resistance", "plan"],
        "strict": True
    }
}

class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5")
        self.timeout_s = int(os.getenv("LLM_TIMEOUT_S", "20"))
        self.client = OpenAI(api_key=self.api_key)

    @staticmethod
    def _hash_payload(di: Dict[str, Any]) -> str:
        payload = json.dumps(di, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def summarize(self, plan_numbers: Dict[str, Any], features: Dict[str, Any]) -> Dict[str, Any]:
        """Kembalikan JSON Analisa SPOT I yang mematuhi schema. Jangan ubah angka dari plan_numbers."""
        # Cache key (opsional di atas Redis, di sini return saja supaya gampang dipasang di repo.py bila mau)
        body = {
            "plan": plan_numbers,
            "features": features
        }
        system = (
            "Anda adalah analis crypto spot. Hasilkan Analisa SPOT I ringkas (maks 2 TP), "
            "dengan menjaga agar angka level/TP/SL TIDAK diubah dari 'plan'."
        )
        user = (
            "Buat Analisa SPOT I dalam Bahasa Indonesia. Isi field JSON sesuai schema. "
            "Singkatkan narasi, dan tambahkan 'signals' dan 'fundamental' ringkas 24–48 jam.\n"
            f"DATA: {json.dumps(body, ensure_ascii=False)}"
        )
        resp = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": ANALISA_SCHEMA
                }
            )
        )
        # OpenAI Python SDK mengembalikan structured output; ambil sebagai dict
        try:
            out = resp.output[0].content[0].text  # fallback jika text container
        except Exception:
            out = getattr(resp, "output", None) or getattr(resp, "choices", [{}])[0]
        # Coerce ke dict
        if isinstance(out, str):
            return json.loads(out)
        if isinstance(out, dict):
            return out
        raise RuntimeError("LLM response parsing failed")
PY

# D) Update worker untuk Hybrid + fitur ringkas
applypatch <<'PATCH'
*** Begin Patch
*** Update File: backend/app/workers/analyze_worker.py
@@
-from .services.market import fetch_bundle
-from .services.rules import Features, score_symbol
-from .services.planner import build_plan
+from .services.market import fetch_bundle
+from .services.rules import Features, score_symbol
+from .services.planner import build_plan
+from .services.llm import LLMClient
+import os

 async def run_analyze(symbol: str, options: dict):
     bundle = await fetch_bundle(symbol, tuple(options.get('tf',["4h","1h","15m"])) )
     feat = Features(bundle).enrich() or Features(bundle)
     score = score_symbol(Features(bundle))
-    plan = build_plan(bundle, Features(bundle), score, options.get('mode','auto'))
-    return plan
+    plan = build_plan(bundle, Features(bundle), score, options.get('mode','auto'))
+
+    # Ringkas fitur minimal untuk LLM (hemat token)
+    f1 = feat.b['1h'].iloc[-1]
+    f15 = feat.b['15m'].iloc[-1]
+    features = {
+        'rsi': {'1h': float(f1.rsi14), '15m': float(f15.rsi14)},
+        'ema_stack_ok': {
+            '1h': bool(f1.ema5>f1.ema20>f1.ema50>f1.ema100>f1.ema200),
+            '15m': bool(f15.ema5>f15.ema20>f15.ema50>f15.ema100>f15.ema200)
+        },
+        'bb_pos': {
+            '1h': 'above_MB' if f1.close>f1.mb else ('near_MB' if abs(f1.close-f1.mb)/max(1e-9,f1.mb)<0.002 else 'below_MB'),
+            '15m': 'above_MB' if f15.close>f15.mb else ('near_MB' if abs(f15.close-f15.mb)/max(1e-9,f15.mb)<0.002 else 'below_MB')
+        },
+        'atr_1h': float(f1.atr14)
+    }
+
+    use_llm = bool(options.get('use_llm', str(os.getenv('USE_LLM','false')).lower()=='true'))
+    if use_llm and os.getenv('OPENAI_API_KEY'):
+        try:
+            llm = LLMClient()
+            llm_json = await llm.summarize(plan_numbers=plan, features=features)
+            # gabungkan narasi llm ke plan (tanpa mengubah angka)
+            plan['bias'] = llm_json.get('bias', plan.get('bias',''))
+            plan['narrative'] = (plan.get('narrative','') + "\n" + llm_json.get('signals','')).strip()
+            plan['signals'] = llm_json.get('signals','')
+            plan['fundamental'] = llm_json.get('fundamental','')
+        except Exception as e:
+            # fallback rules-only jika LLM gagal
+            plan['narrative'] = (plan.get('narrative','') + f"\n[LLM fallback] {e}").strip()
+
+    return plan
*** End Patch
PATCH
```

---

## 2) Patch: Endpoint & deps (inject DB dependency dengan benar)
> Endpoint contoh sebelumnya menggunakan lambda import; kita rapikan.

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Update File: backend/app/deps.py
@@
-from fastapi import Depends
-from sqlalchemy.ext.asyncio import AsyncSession
-from .storage.db import SessionLocal
+from sqlalchemy.ext.asyncio import AsyncSession
+from .storage.db import SessionLocal
@@
 async def get_db() -> AsyncSession:
     async with SessionLocal() as session:
         yield session
*** End Patch
PATCH

applypatch <<'PATCH'
*** Begin Patch
*** Update File: backend/app/main.py
@@
-from fastapi import FastAPI, Depends, HTTPException
+from fastapi import FastAPI, Depends, HTTPException
 from fastapi.middleware.cors import CORSMiddleware
 from sqlalchemy.ext.asyncio import AsyncSession
 from .schemas import AnalyzeIn, PlanOut, PlanPayload
 from .storage.db import init_db
 from .storage import repo
 from .services.locks import LockService
-from ..app.config import settings
+from ..app.config import settings
+from . import deps
@@
-@app.post("/api/analyze")
-async def analyze(data: AnalyzeIn, db: AsyncSession = Depends(lambda: __import__('..').app.deps.get_db())):
+@app.post("/api/analyze")
+async def analyze(data: AnalyzeIn, db: AsyncSession = Depends(deps.get_db)):
@@
-@app.get("/api/plan/{plan_id}")
-async def get_plan(plan_id: int, db: AsyncSession = Depends(lambda: __import__('..').app.deps.get_db())):
+@app.get("/api/plan/{plan_id}")
+async def get_plan(plan_id: int, db: AsyncSession = Depends(deps.get_db)):
*** End Patch
PATCH
```

---

## 3) Patch: Frontend — toggle LLM & tampilkan hasil tambahan

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Update File: frontend/src/app/(components)/AnalyzeForm.tsx
@@
-import {useState} from 'react'
+import {useState} from 'react'
 import {api} from '../api'

-export default function AnalyzeForm({onDone}:{onDone:(plan:any)=>void}){
-  const [symbol,setSymbol]=useState('OPUSDT')
-  const [loading,setLoading]=useState(false)
-  async function submit(){
-    setLoading(true)
-    try{ const {data}=await api.post('/api/analyze',{symbol}) ; onDone(data)} finally{ setLoading(false) }
-  }
+export default function AnalyzeForm({onDone}:{onDone:(plan:any)=>void}){
+  const [symbol,setSymbol]=useState('OPUSDT')
+  const [useLLM,setUseLLM]=useState(true)
+  const [loading,setLoading]=useState(false)
+  async function submit(){
+    setLoading(true)
+    try{ const {data}=await api.post('/api/analyze',{symbol, options:{use_llm:useLLM}}) ; onDone(data)} finally{ setLoading(false) }
+  }
   return (
     <div className="p-4 rounded-2xl shadow bg-white flex gap-2 items-end">
       <div className="flex flex-col">
         <label className="text-sm">Symbol</label>
         <input className="border rounded px-3 py-2" value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())}/>
       </div>
+      <label className="flex items-center gap-2 text-sm">
+        <input type="checkbox" checked={useLLM} onChange={e=>setUseLLM(e.target.checked)} /> Narasi LLM (GPT‑5)
+      </label>
       <button onClick={submit} disabled={loading} className="px-4 py-2 rounded bg-black text-white">{loading?'Analisa…':'Analisa'}</button>
     </div>
   )
 }
*** End Patch
PATCH

applypatch <<'PATCH'
*** Begin Patch
*** Update File: frontend/src/app/(components)/PlanCard.tsx
@@
   return (
     <div className="p-4 rounded-2xl shadow bg-white space-y-2">
       <div className="text-lg font-semibold">{plan.symbol} • v{plan.version} • Skor {p.score}</div>
       <div className="text-sm opacity-70">{new Date(plan.created_at).toLocaleString('id-ID')}</div>
       <div className="whitespace-pre-wrap text-sm">
@@
-        {'\n'}<b>Bacaan Sinyal:</b> {p.narrative}
+        {'\n'}<b>Bacaan Sinyal:</b> {p.signals || p.narrative}
+        {p.fundamental ? ('\n'+'\n'+'\u26A0\uFE0F Fundamental 24–48 jam: '+p.fundamental) : ''}
       </div>
       <button onClick={onUpdate} className="px-3 py-2 rounded bg-zinc-900 text-white">Update</button>
     </div>
   )
 }
*** End Patch
PATCH
```

---

## 4) Test minimal LLM (mock) — optional

```bash
mkdir -p backend/app/tests && cat > backend/app/tests/test_llm_mock.py <<'PY'
import asyncio
from app.services.llm import LLMClient

class DummyLLM(LLMClient):
    async def summarize(self, plan_numbers, features):
        return {
            "bias": "Bullish intraday selama struktur 1H bertahan.",
            "support": plan_numbers["support"],
            "resistance": plan_numbers["resistance"],
            "plan": {
                "pullback": {"entries": plan_numbers["entries"], "invalid": plan_numbers["invalid"], "tp": plan_numbers["tp"]},
                "breakout": {"trigger_limit": [1,1], "retest_zone": "", "sl_fast": plan_numbers["invalid"], "tp": plan_numbers["tp"]}
            },
            "signals": "Volume > MA vol, MACD 1H naik.",
            "fundamental": "DXY melemah, BTC gate OK."
        }

async def _t():
    llm = DummyLLM()
    out = await llm.summarize({"support":[1,2],"resistance":[3,4],"entries":[1.1,1.0],"invalid":0.9,"tp":[3.0,3.5]}, {"rsi":{"1h":60}})
    assert "bias" in out and "plan" in out

def test_dummy_llm():
    asyncio.run(_t())
PY
```

---

## 5) Menjalankan lokal
```bash
cp .env.example .env
# isi OPENAI_API_KEY pada .env

# Redis (opsional; lock punya fallback in-memory)
docker compose up -d redis || true

# Backend
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (terminal lain)
cd frontend && npm install && npm run dev
# Buka http://localhost:3000
```

---

## 6) Validasi alur Hybrid
1) **USE_LLM=true** (di .env) dan centang **Narasi LLM (GPT‑5)** di UI.  
2) Analisa `XRPUSDT` → FE kirim `{symbol, options:{use_llm:true}}`.  
3) Backend: hitung angka (rules) → panggil LLM (schema) → gabungkan narasi → simpan versi.  
4) UI menampilkan **Bias**, **Level**, **PB/BO**, **Invalid**, **TP1–TP2**, **Signals/Fundamental**.  
5) Klik **Update** → versi baru tampil (v2, v3…).

---

## 7) Aturan & Batasan yang Tetap Berlaku
- **LLM hanya merangkum**; angka level/TP/SL dari rules adalah **kebenaran tunggal**.  
- Jika **LLM gagal**, fallback otomatis ke narasi rules; UI tetap menampilkan rencana lengkap.
- **Rate‑limit**: lock per `(user_id, symbol)` (TTL ≥ 20 dtk).  
- **Privasi**: hasil per user tidak terlihat user lain.  
- **Legal**: Analisa untuk edukasi; bukan saran finansial.

---

## 8) Tips Optimasi Biaya & Latensi
- Kirim **fitur ringkas** (≤ 30–60 angka) ke LLM.  
- Gunakan `OPENAI_MODEL=gpt-5-mini` saat beban tinggi, `gpt-5` untuk analisa penting.  
- Implementasikan **LLM cache** di Redis dengan key: `llm:{user_id}:{symbol}:{hash(features+levels)}` TTL 5–10 menit.

---

## 9) Next Step (opsional)
- Tambah **header X-User-ID** untuk multi-user sebenarnya.  
- Tambah **export PDF/JSON** dan notifikasi Telegram.  
- BTC gate nyata: ambil BTCUSDT 15m & cek EMA20 + drop >0.8%/15m.  
- Unit test integrasi end-to-end (mock ccxt & LLM).


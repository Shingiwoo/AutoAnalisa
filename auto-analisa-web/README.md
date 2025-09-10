# Auto Analisa Web (Local)

Proyek contoh: Webpage analisa otomatis SPOT crypto untuk 1–4 user lokal.

## Prasyarat
- Node.js >= 20, npm >= 10
- Python >= 3.11
- Docker (untuk Redis)

## Menjalankan Lokal
1) Salin env contoh:
   
   cp .env.example .env

2) Jalankan Redis via Docker:
   
   docker compose up -d redis

3) Backend (FastAPI):
   
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000

4) Frontend (Next.js):
   
   cd frontend
   npm install
   npm run dev

5) Buka aplikasi:
   
   http://localhost:3000

## Endpoint Utama
- GET http://localhost:8940/api/health
- POST http://localhost:8940/api/analyze { symbol: "OPUSDT" }

## Catatan
- Lock Redis mencegah tabrakan; ada fallback in-memory bila Redis tidak aktif.
- ccxt dipanggil sinkron di dalam fungsi async untuk kesederhanaan lokal.


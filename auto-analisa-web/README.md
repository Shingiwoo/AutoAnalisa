# Auto Analisa Web — Local & Production

Aplikasi analisa otomatis SPOT crypto (FastAPI + Next.js) dengan fitur batas 4 kartu per user, watchlist, chart 5m/15m/1h, macro harian, admin settings/budget, dan hash Argon2.

## Arsitektur Singkat
- Backend: FastAPI (Uvicorn) + SQLite (SQLAlchemy async) + ccxt + (opsional) Redis
- Frontend: Next.js 15 + React 19
- Reverse proxy: Nginx (route `/api/*` ke backend, route lain ke frontend)

---

## Prasyarat
- Node.js >= 20, npm >= 10
- Python >= 3.11
- Nginx (untuk produksi)
- Redis (opsional; disarankan untuk kunci/rate‑limit ringan)

---

## Jalankan Lokal (Dev)
1) Salin env contoh ke root proyek:
   
   cp .env.example .env

2) (Opsional) Redis via Docker:
   
   docker compose up -d redis

3) Backend (FastAPI):
   
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8940

4) Frontend (Next.js):
   
   cd frontend
   npm install
   npm run dev -- -p 3840

5) Buka aplikasi:
   
   http://localhost:3840

Endpoint dev utama:
- GET http://localhost:8940/api/health
- POST http://localhost:8940/api/analyze { symbol: "OPUSDT" }

Catatan dev:
- Lock Redis dipakai jika REDIS_URL tersedia; fallback in‑memory bila tidak ada.
- ccxt blocking dipanggil dari konteks async untuk kesederhanaan (cukup untuk beban ringan).

---

## Deploy Produksi (VPS + systemd + Nginx)

Anda dapat memilih cara cepat (installer.sh) atau langkah manual.

### Opsi A — Installer Otomatis (Direkomendasikan)
Prasyarat: Ubuntu 22.04/24.04, domain aktif yang mengarah ke VPS.

1) Tentukan folder proyek (mis. `/var/www/AutoAnalisa/auto-analisa-web`) dan domain (mis. `analisa.example.com`).
2) Jalankan sebagai root/sudo dari root repo ini:

   sudo bash installer.sh \
     --domain analisa.example.com \
     --project-dir /var/www/AutoAnalisa/auto-analisa-web \
     --user www-data \
     --use-llm true \
     --openai-key "sk-..." \
     --with-ssl \
     --email admin@example.com

Yang dilakukan installer:
- Menyiapkan `.env` produksi (APP_ENV=prod, NEXT_PUBLIC_API_BASE, dll)
- Backend: buat venv dan pasang dependencies
- Frontend: build produksi (NEXT_PUBLIC_API_BASE diarahkan ke `https://<domain>/api`)
- Menulis unit `systemd` backend dan frontend (port default: backend 8940, frontend 3840)
- Menulis site Nginx (reverse proxy + SSL otomatis via certbot opsional)
- Mengaktifkan service dan reload Nginx

Setelah selesai, verifikasi:

   curl -fsS http://127.0.0.1:8940/api/health
   curl -k -fsS https://analisa.example.com/api/health

Masuk ke UI: `https://analisa.example.com`

### Opsi B — Langkah Manual
1) Siapkan folder & user:
   - Contoh: `/var/www/AutoAnalisa/auto-analisa-web`, owner `www-data:www-data`
   - Pastikan struktur `backend/` dan `frontend/` ada (repo ini)

2) ENV produksi (`.env` di root repo):
   - Salin dari `.env.example` lalu set:
     - `APP_ENV=prod`
     - `JWT_SECRET` = string acak panjang
     - `OPENAI_API_KEY` (jika pakai LLM), `USE_LLM=true` (opsional)
     - `CORS_ORIGINS=https://analisa.example.com` (batasi CORS di prod)
     - `SQLITE_URL` – aman memakai relatif `sqlite+aiosqlite:///./app.db` (WorkingDirectory backend = `backend`). Untuk path absolut: `sqlite+aiosqlite:////var/www/AutoAnalisa/auto-analisa-web/backend/app.db`.
     - `NEXT_PUBLIC_API_BASE` kosongkan (FE akan gunakan relatif `/api`) atau isi `https://analisa.example.com`.

3) Backend (venv + dependencies):

   cd /var/www/AutoAnalisa/auto-analisa-web/backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -U pip wheel setuptools
   pip install -r requirements.txt
   # Inisialisasi tabel (opsional, backend akan create otomatis saat start)
   python scripts/migrate_init.py
   deactivate

4) Frontend (build):

   cd /var/www/AutoAnalisa/auto-analisa-web/frontend
   export NEXT_PUBLIC_API_BASE=https://analisa.example.com
   npm ci || npm install
   npm run build

5) systemd service:
   - Contoh unit tersedia di `deploy/systemd/`. Sesuaikan `WorkingDirectory`, port, dan `EnvironmentFile`:
     - Backend: `auto-analisa-web/deploy/systemd/auto-analisa-backend.service`
     - Frontend: `auto-analisa-web/deploy/systemd/auto-analisa-frontend.service`

   Salin dan aktifkan:

   sudo cp deploy/systemd/auto-analisa-backend.service /etc/systemd/system/
   sudo cp deploy/systemd/auto-analisa-frontend.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now auto-analisa-backend auto-analisa-frontend

6) Nginx reverse proxy:
   - Contoh site: `deploy/nginx/analisa.example.com.conf` (route `/api/` ke backend, lainnya ke frontend)
   - Edit `server_name` dan sesuaikan upstream port jika berbeda

   sudo cp deploy/nginx/analisa.example.com.conf /etc/nginx/sites-available/analisa.example.com.conf
   sudo ln -s /etc/nginx/sites-available/analisa.example.com.conf /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx

7) SSL (opsional namun direkomendasikan):

   sudo certbot --nginx -d analisa.example.com -m admin@example.com --agree-tos --redirect

8) Buat admin user:
   - Cara 1 (script):

     cd /var/www/AutoAnalisa/auto-analisa-web
     PYTHONPATH=$(pwd)/backend backend/.venv/bin/python backend/scripts/make_admin.py admin@example.com PasswordKuat123

     Catatan: jika path instalasi berbeda dari script, sesuaikan `BACKEND_DIR` di file script atau gunakan `PYTHONPATH` seperti di atas.

   - Cara 2 (via Register jika diizinkan), lalu ubah role ke `admin` langsung di DB SQLite (opsional).

9) Smoke test:
   - `curl -fsS http://127.0.0.1:<port backend>/api/health` → harus `{ "ok": true }`
   - Buka UI, login, lihat kartu aktif termuat, watchlist berfungsi, dan analyze berjalan.

---

## Operasional & Tips
- Matikan/aktifkan LLM & budget via halaman Admin.
- Rate‑limit ringan diterapkan pada `/api/analyze` dan `/api/ohlcv`.
- Set `CORS_ORIGINS` ke domain FE produksi jika `APP_ENV=prod`.
- Gunakan Redis untuk cache/rate‑limit lebih stabil (set `REDIS_URL`).
- Update versi: pull repo, rebuild FE (`npm run build`), restart service.


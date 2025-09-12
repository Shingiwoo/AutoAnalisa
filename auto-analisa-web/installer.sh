#!/usr/bin/env bash
set -euo pipefail

# ==============================================
# Auto Installer — auto-analisa-web (Hybrid GPT‑5)
# Ubuntu 22.04/24.04 • Nginx reverse proxy • Redis • systemd
# Tidak mengganggu situs lain (WordPress/Laravel) — buat server_name baru
# ==============================================
# Usage contoh:
#   sudo bash installer.sh \
#     --domain webanalisa.appshin.xyz \
#     --project-dir /var/www/AutoAnalisa/auto-analisa-web \
#     --user www-data \
#     --use-llm true \
#     --openai-key "sk-..." \
#     --with-ssl \
#     --email admin@example.com
#
# Minimal:
#   sudo bash installer.sh --domain webanalisa.appshin.xyz --project-dir /var/www/AutoAnalisa/auto-analisa-web
# ==============================================

DOMAIN=""
PROJECT_DIR=""
RUN_USER="www-data"
USE_LLM="false"
OPENAI_KEY=""
WITH_SSL="false"
EMAIL=""
BACKEND_PORT=8940
FRONTEND_PORT=3840

log(){ echo -e "\e[1;32m[installer]\e[0m $*"; }
err(){ echo -e "\e[1;31m[error]\e[0m $*" >&2; }

# ---- parse args ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --project-dir) PROJECT_DIR="$2"; shift 2 ;;
    --user) RUN_USER="$2"; shift 2 ;;
    --use-llm) USE_LLM="$2"; shift 2 ;;
    --openai-key) OPENAI_KEY="$2"; shift 2 ;;
    --with-ssl) WITH_SSL="true"; shift 1 ;;
    --email) EMAIL="$2"; shift 2 ;;
    *) err "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then err "Jalankan dengan sudo/root"; exit 1; fi
if [[ -z "$DOMAIN" || -z "$PROJECT_DIR" ]]; then
  err "Wajib: --domain dan --project-dir"; exit 1
fi

log "Domain        : $DOMAIN"
log "Project dir   : $PROJECT_DIR"
log "Run user      : $RUN_USER"
log "USE_LLM       : $USE_LLM"
log "WITH_SSL      : $WITH_SSL"
[[ -n "$OPENAI_KEY" ]] && log "OPENAI_KEY     : (provided)" || log "OPENAI_KEY     : (empty)"
[[ -n "$EMAIL" ]] && log "Let's Encrypt  : email=$EMAIL" || true

# ---- prerequisites ----
log "Install prerequisite packages (Node 22, Python venv, Redis, Nginx, Certbot)"
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release software-properties-common

if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
else
  log "Node sudah terpasang: $(node -v)"
fi

apt-get install -y python3-venv python3-dev
apt-get install -y nginx redis-server certbot python3-certbot-nginx jq || true

systemctl enable --now redis-server || true

# ---- sanity checks ----
if [[ ! -d "$PROJECT_DIR/backend" || ! -d "$PROJECT_DIR/frontend" ]]; then
  err "Struktur proyek tidak lengkap di $PROJECT_DIR. Pastikan ada backend/ dan frontend/"; exit 1
fi

# ---- prepare env (.env di root) ----
log "Menyiapkan .env di root proyek"
ENV_FILE="$PROJECT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$PROJECT_DIR/.env.example" "$ENV_FILE" || true
fi
SECRET_KEY=$(openssl rand -hex 16)
API_BASE="https://$DOMAIN/api"

# tulis/update kunci penting
sed -i "/^APP_ENV=/d;/^SECRET_KEY=/d;/^SQLITE_URL=/d;/^REDIS_URL=/d;/^USE_LLM=/d;/^OPENAI_API_KEY=/d;/^OPENAI_MODEL=/d;/^LLM_TIMEOUT_S=/d;/^LLM_CACHE_TTL_S=/d;/^NEXT_PUBLIC_API_BASE=/d" "$ENV_FILE"
cat >> "$ENV_FILE" <<EOF
APP_ENV=prod
SECRET_KEY=$SECRET_KEY
SQLITE_URL=sqlite+aiosqlite:///./app.db
REDIS_URL=redis://localhost:6379/0
USE_LLM=$USE_LLM
OPENAI_API_KEY=$OPENAI_KEY
OPENAI_MODEL=gpt-5-chat-latest
LLM_TIMEOUT_S=20
LLM_CACHE_TTL_S=300
NEXT_PUBLIC_API_BASE=$API_BASE
EOF

chown $RUN_USER:$RUN_USER "$ENV_FILE" || true
chmod 640 "$ENV_FILE" || true

# ---- backend setup ----
log "Setup backend venv & dependencies"
cd "$PROJECT_DIR/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip wheel setuptools
pip install -r requirements.txt
deactivate

# ---- frontend build (pakai API_BASE) ----
log "Build frontend (Next.js)"
cd "$PROJECT_DIR/frontend"
su -s /bin/bash "$RUN_USER" -c "cd $PROJECT_DIR/frontend && export NEXT_PUBLIC_API_BASE=$API_BASE && npm ci || npm install"
su -s /bin/bash "$RUN_USER" -c "cd $PROJECT_DIR/frontend && export NEXT_PUBLIC_API_BASE=$API_BASE && npm run build"

# ---- systemd units ----
log "Membuat systemd unit files"
BACK_UNIT=/etc/systemd/system/auto-analisa-backend.service
FRONT_UNIT=/etc/systemd/system/auto-analisa-frontend.service

cat > "$BACK_UNIT" <<EOF
[Unit]
Description=Auto Analisa Web - Backend (Uvicorn)
After=network.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$PROJECT_DIR/backend
Environment=PYTHONUNBUFFERED=1
Environment=APP_ENV=prod
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT
Restart=always
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
EOF

cat > "$FRONT_UNIT" <<EOF
[Unit]
Description=Auto Analisa Web - Frontend (Next.js)
After=network.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$PROJECT_DIR/frontend
Environment=NODE_ENV=production
Environment=PORT=$FRONTEND_PORT
Environment=NEXT_PUBLIC_API_BASE=$API_BASE
ExecStart=/usr/bin/npm run start --silent
Restart=always
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now auto-analisa-backend auto-analisa-frontend
sleep 2
systemctl --no-pager --full status auto-analisa-backend | sed -n '1,20p' || true
systemctl --no-pager --full status auto-analisa-frontend | sed -n '1,20p' || true

# ---- nginx site (baru, tidak mengubah situs lain) ----
log "Menulis Nginx site baru untuk $DOMAIN"
SITE_FILE="/etc/nginx/sites-available/$DOMAIN.conf"
if [[ -f "/etc/nginx/sites-enabled/$DOMAIN.conf" || -f "$SITE_FILE" ]]; then
  cp "$SITE_FILE" "$SITE_FILE.bak.$(date +%s)" || true
fi

cat > "$SITE_FILE" <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location ^~ /.well-known/acme-challenge/ { root /var/www/html; allow all; }
    return 301 https://\$host\$request_uri;
}

upstream auto_analisa_backend { server 127.0.0.1:$BACKEND_PORT; }
upstream auto_analisa_frontend { server 127.0.0.1:$FRONTEND_PORT; }

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    # Sertifikat akan dibuat dengan certbot jika --with-ssl digunakan
    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers ringkas
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # API ➜ backend
    location /api/ {
        proxy_pass http://auto_analisa_backend;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout  3600s;
        proxy_send_timeout  3600s;
    }

    # Frontend ➜ next start
    location / {
        proxy_pass http://auto_analisa_frontend;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Lindungi file sensitif
    location ~ /\.(?!well-known) { deny all; }
    location ~* \.env(\..*)?$ { deny all; }
}
EOF

ln -sf "$SITE_FILE" "/etc/nginx/sites-enabled/$DOMAIN.conf"
nginx -t && systemctl reload nginx

# ---- SSL issuance (opsional) ----
if [[ "$WITH_SSL" == "true" ]]; then
  if [[ -z "$EMAIL" ]]; then
    err "--with-ssl but no --email provided. Lewati issuance. Jalankan manual: certbot --nginx -d $DOMAIN";
  else
    log "Menjalankan Certbot untuk $DOMAIN"
    certbot --nginx -n --agree-tos -m "$EMAIL" -d "$DOMAIN" --redirect || true
    nginx -t && systemctl reload nginx || true
  fi
fi

# ---- quick tests ----
log "Tes backend lokal: curl -f http://127.0.0.1:$BACKEND_PORT/api/health"
if curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/health" | grep -q '"ok": true'; then
  log "Backend OK"
else
  err "Backend tidak merespon health. Cek: journalctl -u auto-analisa-backend -f"; fi

log "Tes via domain (mungkin gagal jika SSL belum siap): curl -k -fsS https://$DOMAIN/api/health || true"
curl -k -fsS "https://$DOMAIN/api/health" || true

log "Selesai. Buka https://$DOMAIN dan jalankan analisa."
log "Troubleshoot: journalctl -u auto-analisa-backend -f | journalctl -u auto-analisa-frontend -f | nginx -t"

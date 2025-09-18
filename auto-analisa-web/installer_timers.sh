#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# Installer Timers — Macro (pagi/malam) & Futures Refresh
# Hanya memasang unit systemd timer untuk AutoAnalisa.
#
# Contoh:
#   sudo bash installer_timers.sh \
#     --project-dir /var/www/AutoAnalisa/auto-analisa-web \
#     --user www-data
#
# Opsi:
#   --project-dir   Path root proyek (wajib)
#   --user          User untuk menjalankan service (default: www-data)
#   --macro         true|false (default: true)
#   --futures       true|false (default: true)
#   --pybin         Path python venv (default: <project>/backend/.venv/bin/python)
#   --env-file      Path .env (default: <project>/.env bila ada)
# ==========================================================

RUN_USER="www-data"
PROJECT_DIR=""
ENABLE_MACRO="true"
ENABLE_FUTURES="true"
PYBIN=""
ENV_FILE=""

log(){ echo -e "\e[1;32m[timers]\e[0m $*"; }
err(){ echo -e "\e[1;31m[error]\e[0m $*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir) PROJECT_DIR="$2"; shift 2 ;;
    --user) RUN_USER="$2"; shift 2 ;;
    --macro) ENABLE_MACRO="$2"; shift 2 ;;
    --futures) ENABLE_FUTURES="$2"; shift 2 ;;
    --pybin) PYBIN="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    *) err "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then err "Jalankan dengan sudo/root"; exit 1; fi
if [[ -z "$PROJECT_DIR" ]]; then err "--project-dir wajib"; exit 1; fi
if [[ ! -d "$PROJECT_DIR/backend" ]]; then err "Backend tidak ditemukan di $PROJECT_DIR/backend"; exit 1; fi

# Default PYBIN & ENV
if [[ -z "$PYBIN" ]]; then PYBIN="$PROJECT_DIR/backend/.venv/bin/python"; fi
if [[ -z "$ENV_FILE" && -f "$PROJECT_DIR/.env" ]]; then ENV_FILE="$PROJECT_DIR/.env"; fi

log "Project dir   : $PROJECT_DIR"
log "Run user      : $RUN_USER"
log "Macro timer   : $ENABLE_MACRO"
log "Futures timer : $ENABLE_FUTURES"
log "PYBIN         : $PYBIN (fallback to python3 jika tidak ada)"
[[ -n "$ENV_FILE" ]] && log "Env file      : $ENV_FILE" || log "Env file      : (none)"

SYSTEMD_DIR="/etc/systemd/system"
BACK_DIR="$PROJECT_DIR/backend"

make_macro_unit(){
  local svc="$SYSTEMD_DIR/autoanalisa-macro.service"
  local tmr="$SYSTEMD_DIR/autoanalisa-macro.timer"
  log "Menulis unit Macro: $svc $tmr"
  cat > "$svc" <<EOF
[Unit]
Description=Auto Analisa Web - Macro Daily Generator
After=network.target

[Service]
Type=oneshot
WorkingDirectory=$BACK_DIR
Environment=APP_ENV=prod
$( [[ -n "$ENV_FILE" ]] && echo "EnvironmentFile=$ENV_FILE" )
Environment=PYBIN=$PYBIN
ExecStart=/bin/bash -lc 'PY=${PYBIN}; if [ ! -x "$PY" ]; then PY=$(command -v python3); fi; export PYTHONPATH=$PWD; exec "$PY" scripts/macro_generate.py'
User=$RUN_USER
Group=$RUN_USER

[Install]
WantedBy=multi-user.target
EOF

  cat > "$tmr" <<'EOF'
[Unit]
Description=Run Macro Daily Generator at 00:05 and 18:05 WIB

[Timer]
OnCalendar=*-*-* 00:05:00
OnCalendar=*-*-* 18:05:00
Persistent=true
Unit=autoanalisa-macro.service

[Install]
WantedBy=timers.target
EOF
}

make_futures_unit(){
  local svc="$SYSTEMD_DIR/autoanalisa-futures-refresh.service"
  local tmr="$SYSTEMD_DIR/autoanalisa-futures-refresh.timer"
  log "Menulis unit Futures Refresh: $svc $tmr"
  cat > "$svc" <<EOF
[Unit]
Description=Auto Analisa Web - Futures Signals Refresh
After=network.target

[Service]
Type=oneshot
WorkingDirectory=$BACK_DIR
Environment=APP_ENV=prod
$( [[ -n "$ENV_FILE" ]] && echo "EnvironmentFile=$ENV_FILE" )
Environment=PYBIN=$PYBIN
ExecStart=/bin/bash -lc 'PY=${PYBIN}; if [ ! -x "$PY" ]; then PY=$(command -v python3); fi; export PYTHONPATH=$PWD; exec "$PY" scripts/futures_refresh.py'
User=$RUN_USER
Group=$RUN_USER

[Install]
WantedBy=multi-user.target
EOF

  cat > "$tmr" <<'EOF'
[Unit]
Description=Run Futures Signals Refresh every 10 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Persistent=true
Unit=autoanalisa-futures-refresh.service

[Install]
WantedBy=timers.target
EOF
}

log "Menulis unit timer..."
[[ "$ENABLE_MACRO" == "true" ]] && make_macro_unit || log "Lewati Macro"
[[ "$ENABLE_FUTURES" == "true" ]] && make_futures_unit || log "Lewati Futures"

log "Reload systemd dan enable timers"
systemctl daemon-reload
[[ "$ENABLE_MACRO" == "true" ]] && systemctl enable --now autoanalisa-macro.timer || true
[[ "$ENABLE_FUTURES" == "true" ]] && systemctl enable --now autoanalisa-futures-refresh.timer || true

log "Status singkat (abaikan error bila unit tertentu dinonaktifkan)"
( systemctl --no-pager --full status autoanalisa-macro.timer | sed -n '1,12p' ) || true
( systemctl --no-pager --full status autoanalisa-futures-refresh.timer | sed -n '1,12p' ) || true

log "Selesai. Gunakan 'journalctl -u autoanalisa-macro.service -f' dan 'journalctl -u autoanalisa-futures-refresh.service -f' untuk log."


#!/usr/bin/env python3
import os, sys
from uuid import uuid4
from pathlib import Path

# Ensure repo root (/app) is on sys.path when running inside container
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _get_sync_url():
    """Resolve target DB URL for admin creation.
    - Prefer DATABASE_URL (required for MySQL-only deployments)
    - Convert async drivers to sync (aiomysql->pymysql, asyncpg->psycopg2)
    - Refuse to use SQLite to avoid writing to the wrong file when deployment is MySQL-only
    """
    # 1) From env first (preferred in Docker/containerized runtime)
    url = os.getenv("DATABASE_URL")
    # 2) From app settings if available
    if not url:
        try:
            from app.config import settings  # type: ignore
            url = getattr(settings, "DATABASE_URL", None)
        except Exception:
            url = None
    if not url:
        raise SystemExit("ERROR: DATABASE_URL is not set. Run inside backend container or export DATABASE_URL.")
    # Normalize drivers for sync engine
    url_sync = (
        url.replace("sqlite+aiosqlite", "sqlite")
           .replace("mysql+aiomysql", "mysql+pymysql")
           .replace("postgresql+asyncpg", "postgresql+psycopg2")
    )
    # Disallow SQLite for admin creation in MySQL-only deployments
    if url_sync.startswith("sqlite:"):
        raise SystemExit("ERROR: Refusing to use SQLite. Set DATABASE_URL to your MySQL DSN or run: docker compose exec backend python scripts/make_admin.py <email> <password>")
    return url_sync

from sqlalchemy import create_engine, text, inspect
from datetime import datetime
try:
    from passlib.hash import argon2
except Exception:
    argon2 = None  # will error later if missing

def _ensure_user_columns(engine):
    """Ensure new columns exist for backward compatibility (approved, blocked).
    Works for SQLite/MySQL. No-op if columns already present."""
    try:
        insp = inspect(engine)
        cols = {c['name'] for c in insp.get_columns('users')}
    except Exception:
        # Fallback probing for SQLite
        try:
            with engine.connect() as conn:
                res = conn.execute(text("PRAGMA table_info(users)"))
                cols = {row[1] for row in res}
        except Exception:
            cols = set()
    statements = []
    if 'approved' not in cols:
        statements.append("ALTER TABLE users ADD COLUMN approved BOOLEAN DEFAULT 1")
    if 'blocked' not in cols:
        statements.append("ALTER TABLE users ADD COLUMN blocked BOOLEAN DEFAULT 0")
    for stmt in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            # Ignore if backend doesn't support or column already added concurrently
            pass

def main(email: str, password: str):
    url = _get_sync_url()
    engine = create_engine(url, future=True)
    # ensure columns exist and table exists
    _ensure_user_columns(engine)
    pwd_hash = argon2.hash(password) if argon2 else password
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with engine.begin() as conn:
        # Create table users if not exists (minimal schema)
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS users (
              id VARCHAR(64) PRIMARY KEY,
              email VARCHAR(255) UNIQUE NOT NULL,
              password_hash VARCHAR(255) NOT NULL,
              `role` VARCHAR(32) NOT NULL DEFAULT 'user',
              approved TINYINT(1) DEFAULT 1,
              blocked TINYINT(1) DEFAULT 0,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            """
        ))
        # Ensure columns present (idempotent)
        _ensure_user_columns(engine)
        # Upsert by email
        res = conn.execute(text("SELECT id FROM users WHERE email=:e"), {"e": email})
        row = res.first()
        if row:
            conn.execute(
                text("UPDATE users SET password_hash=:ph, `role`='admin', approved=1, blocked=0 WHERE email=:e"),
                {"ph": pwd_hash, "e": email},
            )
            action = "UPDATED"
        else:
            conn.execute(
                text(
                    "INSERT INTO users (id,email,password_hash,`role`,approved,blocked,created_at) "
                    "VALUES (:id,:e,:ph,'admin',1,0,:ts)"
                ),
                {"id": str(uuid4()), "e": email, "ph": pwd_hash, "ts": now},
            )
            action = "CREATED"
    print(f"OK [{action}] admin: {email}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make_admin.py <email> <password>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

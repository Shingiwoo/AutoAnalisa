#!/usr/bin/env python3
import os, sys
from uuid import uuid4

# pastikan backend ada di sys.path
BACKEND_DIR = '/var/www/AutoAnalisa/auto-analisa-web/backend'
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

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
from sqlalchemy.orm import sessionmaker
from app.models import Base, User
from app.auth import hash_pw

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
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    # pastikan tabel ada
    Base.metadata.create_all(engine)
    # ensure backward-compatible columns exist
    _ensure_user_columns(engine)

    with SessionLocal() as s:
        u = s.query(User).filter_by(email=email).first()
        if u:
            u.password_hash = hash_pw(password)
            u.role = "admin"
            try:
                u.approved = True  # type: ignore
                u.blocked = False  # type: ignore
            except Exception:
                pass
            action = "UPDATED"
        else:
            kwargs = dict(id=str(uuid4()), email=email, password_hash=hash_pw(password), role="admin")
            # Populate moderation flags if model supports them
            try:
                kwargs.update(approved=True, blocked=False)
            except Exception:
                pass
            u = User(**kwargs)  # type: ignore[arg-type]
            s.add(u)
            action = "CREATED"
        s.commit()
        print(f"OK [{action}] admin: {u.email}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make_admin.py <email> <password>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

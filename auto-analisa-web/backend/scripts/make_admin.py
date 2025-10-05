#!/usr/bin/env python3
import os, sys
from uuid import uuid4

# pastikan backend ada di sys.path
BACKEND_DIR = '/var/www/AutoAnalisa/auto-analisa-web/backend'
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# DB URL: ambil dari settings kalau ada, fallback ke ENV/.env atau default sqlite
def _get_sqlite_url():
    try:
        from app.config import settings  # project kamu biasanya punya ini
        url = getattr(settings, "DATABASE_URL", None) or getattr(settings, "SQLITE_URL", "sqlite:///app.db")
    except Exception:
        url = os.getenv("DATABASE_URL") or os.getenv("SQLITE_URL", "sqlite:///app.db")
    # Swap async drivers to sync equivalents when needed
    return url.replace("sqlite+aiosqlite", "sqlite").replace("mysql+aiomysql", "mysql+pymysql")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User
from app.auth import hash_pw

def main(email: str, password: str):
    url = _get_sqlite_url()
    engine = create_engine(url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    # pastikan tabel ada
    Base.metadata.create_all(engine)

    with SessionLocal() as s:
        u = s.query(User).filter_by(email=email).first()
        if u:
            u.password_hash = hash_pw(password)
            u.role = "admin"
            action = "UPDATED"
        else:
            u = User(id=str(uuid4()), email=email, password_hash=hash_pw(password), role="admin")
            s.add(u)
            action = "CREATED"
        s.commit()
        print(f"OK [{action}] admin: {u.email}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make_admin.py <email> <password>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

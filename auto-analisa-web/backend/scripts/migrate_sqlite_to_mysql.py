#!/usr/bin/env python3
"""
Migrate data from an existing SQLite file to a target SQL database (MySQL recommended).

Usage:
  python scripts/migrate_sqlite_to_mysql.py --sqlite /host/path/app.db \
      --target mysql+pymysql://user:pass@host:3306/autoanalisa

If --target is omitted, reads DATABASE_URL from env; falls back to SQLITE_URL.

This script uses SQLAlchemy ORM models in app.models so columns are mapped consistently.
It creates target tables if missing, disables FK checks during copy, and uses session.merge
to avoid duplicates.
"""
import argparse
import os
from typing import List

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import sys
import pathlib

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import Base  # noqa: E402


def _mk_sqlite_url(path: str) -> str:
    # Accept bare path or sqlite:/// URL
    if path.startswith("sqlite:"):
        return path.replace("sqlite+aiosqlite", "sqlite")
    # Ensure absolute path (3 slashes for relative, 4 for absolute)
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = (pathlib.Path.cwd() / p).resolve()
    return f"sqlite:///{p}"


def _mk_target_url(url: str) -> str:
    # Swap async drivers for sync if needed
    return (
        url.replace("sqlite+aiosqlite", "sqlite")
        .replace("mysql+aiomysql", "mysql+pymysql")
        .replace("postgresql+asyncpg", "postgresql+psycopg2")
    )


def _all_mapped_classes() -> List[type]:
    return [m.class_ for m in Base.registry.mappers]


def main():
    ap = argparse.ArgumentParser(description="SQLite -> SQL (MySQL) migrator")
    ap.add_argument("--sqlite", required=True, help="Path to existing SQLite .db file")
    ap.add_argument(
        "--target",
        default=os.getenv("DATABASE_URL") or os.getenv("SQLITE_URL"),
        help="Target SQLAlchemy URL (e.g., mysql+pymysql://user:pass@host:3306/autoanalisa)",
    )
    args = ap.parse_args()

    if not args.target:
        print("ERROR: --target or env DATABASE_URL/SQLITE_URL is required", file=sys.stderr)
        sys.exit(2)

    src_url = _mk_sqlite_url(args.sqlite)
    dst_url = _mk_target_url(args.target)

    print(f"Source: {src_url}")
    print(f"Target: {dst_url}")

    src_engine = create_engine(src_url, future=True)
    dst_engine = create_engine(dst_url, future=True)

    Base.metadata.create_all(dst_engine)

    # Disable FK checks if target is MySQL
    backend = dst_engine.url.get_backend_name()
    disable_fk = backend.startswith("mysql")

    classes = sorted(_all_mapped_classes(), key=lambda c: getattr(c, "__tablename__", c.__name__))

    with src_engine.connect() as sconn, dst_engine.begin() as dconn:
        if disable_fk:
            dconn.execute(text("SET FOREIGN_KEY_CHECKS=0"))

        with Session(bind=sconn) as s, Session(bind=dconn) as d:
            for cls in classes:
                tname = getattr(cls, "__tablename__", cls.__name__)
                try:
                    rows = s.query(cls).all()
                except Exception as e:  # table may not exist in source
                    print(f"Skip {tname}: {e}")
                    continue
                if not rows:
                    print(f"{tname}: 0 rows")
                    continue
                count = 0
                for r in rows:
                    # Build a plain dict of column values
                    data = {}
                    for col in cls.__table__.columns:  # type: ignore[attr-defined]
                        try:
                            data[col.name] = getattr(r, col.name)
                        except Exception:
                            pass
                    d.merge(cls(**data))
                    count += 1
                print(f"{tname}: migrated {count} rows")

        if disable_fk:
            dconn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    print("DONE: migration completed")


if __name__ == "__main__":
    main()

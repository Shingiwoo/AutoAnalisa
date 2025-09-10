import os, sys
from sqlalchemy import create_engine

# Ensure backend root is on sys.path when running the script directly
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.models import Base

SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///app.db").replace("sqlite+aiosqlite", "sqlite")
engine = create_engine(SQLITE_URL)
Base.metadata.create_all(engine)
print("OK: tables created")

import os
from sqlalchemy import create_engine
from app.models import Base

SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///app.db").replace("sqlite+aiosqlite", "sqlite")
engine = create_engine(SQLITE_URL)
Base.metadata.create_all(engine)
print("OK: tables created")


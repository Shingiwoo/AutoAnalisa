import sys, os
import pytest

# Tambahkan path modul 'app' agar import berhasil saat pytest dijalankan dari root proyek
THIS_DIR = os.path.dirname(__file__)
# Tambahkan folder 'backend' ke sys.path sehingga package 'app' dapat ditemukan
BACKEND_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))  # points to: backend
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

"""Pytest bootstrap.
- Set DB ke lokasi writable (bukan app.db produksi) agar test tidak terkena readonly.
"""
# Set sebelum import modul DB
# Use a SQLite file inside the workspace to satisfy sandbox write limits
os.environ.setdefault("SQLITE_URL", "sqlite+aiosqlite:///./test_app.db")

# Pastikan DB terinisialisasi sebelum test berjalan
from app.storage.db import init_db


@pytest.fixture(scope="session", autouse=True)
def _init_db_session():
    # Allow skipping DB init for lightweight/unit-only runs
    if os.getenv("AUTOANALISA_INIT_DB", "1") != "1":
        return
    import asyncio
    asyncio.get_event_loop().run_until_complete(init_db())

from sqlalchemy.ext.asyncio import AsyncSession
from .storage.db import SessionLocal


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            # Pastikan rollback agar tidak meninggalkan PendingRollback
            try:
                await session.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                await session.close()
            except Exception:
                pass

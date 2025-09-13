from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .. import models
from ..config import settings


engine = create_async_engine(settings.SQLITE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        # lightweight migrations for SQLite
        try:
            res = await conn.exec_driver_sql("PRAGMA table_info(settings)")
            cols = {row[1] for row in res.fetchall()}
            if "registration_enabled" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN registration_enabled BOOLEAN DEFAULT 1"
                )
            if "max_users" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN max_users INTEGER DEFAULT 4"
                )
            if "enable_fvg" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN enable_fvg BOOLEAN DEFAULT 0"
                )
            if "enable_supply_demand" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN enable_supply_demand BOOLEAN DEFAULT 0"
                )
        except Exception:
            pass

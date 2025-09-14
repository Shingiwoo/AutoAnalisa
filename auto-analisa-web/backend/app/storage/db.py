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
            if "fvg_use_bodies" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN fvg_use_bodies BOOLEAN DEFAULT 0"
                )
            if "fvg_fill_rule" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN fvg_fill_rule TEXT DEFAULT 'any_touch'"
                )
            if "sd_max_base" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN sd_max_base INTEGER DEFAULT 3"
                )
            if "sd_body_ratio" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN sd_body_ratio FLOAT DEFAULT 0.33"
                )
            if "sd_min_departure" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN sd_min_departure FLOAT DEFAULT 1.5"
                )
            if "fvg_threshold_pct" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN fvg_threshold_pct FLOAT DEFAULT 0.0"
                )
            if "fvg_threshold_auto" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN fvg_threshold_auto BOOLEAN DEFAULT 0"
                )
            if "fvg_tf" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN fvg_tf TEXT DEFAULT '15m'"
                )
            if "sd_mode" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN sd_mode TEXT DEFAULT 'swing'"
                )
            if "sd_vol_div" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN sd_vol_div INTEGER DEFAULT 20"
                )
            if "sd_vol_threshold_pct" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN sd_vol_threshold_pct FLOAT DEFAULT 10.0"
                )
            if "show_sessions_hint" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN show_sessions_hint BOOLEAN DEFAULT 1"
                )
            if "default_weight_profile" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN default_weight_profile TEXT DEFAULT 'DCA'"
                )
        except Exception:
            pass
        try:
            res2 = await conn.exec_driver_sql("PRAGMA table_info(macro_daily)")
            cols_m = {row[1] for row in res2.fetchall()}
            if "sections" not in cols_m:
                # SQLite lacks proper JSON type; TEXT acceptable, clients treat as JSON
                await conn.exec_driver_sql(
                    "ALTER TABLE macro_daily ADD COLUMN sections JSON DEFAULT '[]'"
                )
            if "slot" not in cols_m:
                await conn.exec_driver_sql(
                    "ALTER TABLE macro_daily ADD COLUMN slot TEXT DEFAULT 'pagi'"
                )
            if "last_run_status" not in cols_m:
                await conn.exec_driver_sql(
                    "ALTER TABLE macro_daily ADD COLUMN last_run_status TEXT DEFAULT 'ok'"
                )
        except Exception:
            pass

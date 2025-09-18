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
            if "llm_daily_limit_spot" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN llm_daily_limit_spot INTEGER DEFAULT 40"
                )
            if "llm_daily_limit_futures" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN llm_daily_limit_futures INTEGER DEFAULT 40"
                )
            # Futures settings additions
            if "enable_futures" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN enable_futures BOOLEAN DEFAULT 0"
                )
            if "futures_leverage_min" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_leverage_min INTEGER DEFAULT 3"
                )
            if "futures_leverage_max" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_leverage_max INTEGER DEFAULT 10"
                )
            if "futures_risk_per_trade_pct" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_risk_per_trade_pct FLOAT DEFAULT 0.5"
                )
            if "futures_funding_threshold_bp" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_funding_threshold_bp FLOAT DEFAULT 3.0"
                )
            if "futures_funding_avoid_minutes" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_funding_avoid_minutes INTEGER DEFAULT 10"
                )
            if "futures_liq_buffer_k_atr15m" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_liq_buffer_k_atr15m FLOAT DEFAULT 0.5"
                )
            if "futures_default_weight_profile" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_default_weight_profile TEXT DEFAULT 'DCA'"
                )
            if "futures_funding_alert_enabled" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_funding_alert_enabled BOOLEAN DEFAULT 1"
                )
            if "futures_funding_alert_window_min" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE settings ADD COLUMN futures_funding_alert_window_min INTEGER DEFAULT 30"
                )
        except Exception:
            pass
        # llm_verifications: add JSON fields if missing
        try:
            res3 = await conn.exec_driver_sql("PRAGMA table_info(llm_verifications)")
            cols_v = {row[1] for row in res3.fetchall()}
            if "suggestions" not in cols_v:
                await conn.exec_driver_sql(
                    "ALTER TABLE llm_verifications ADD COLUMN suggestions JSON DEFAULT '{}'"
                )
            if "fundamentals" not in cols_v:
                await conn.exec_driver_sql(
                    "ALTER TABLE llm_verifications ADD COLUMN fundamentals JSON DEFAULT '{}'"
                )
            if "spot2_json" not in cols_v:
                await conn.exec_driver_sql(
                    "ALTER TABLE llm_verifications ADD COLUMN spot2_json JSON DEFAULT '{}'"
                )
            if "cached" not in cols_v:
                await conn.exec_driver_sql(
                    "ALTER TABLE llm_verifications ADD COLUMN cached BOOLEAN DEFAULT 0"
                )
            if "futures_json" not in cols_v:
                await conn.exec_driver_sql(
                    "ALTER TABLE llm_verifications ADD COLUMN futures_json JSON DEFAULT '{}'"
                )
        except Exception:
            pass
        # llm_usage add kind
        try:
            resu = await conn.exec_driver_sql("PRAGMA table_info(llm_usage)")
            cols_u = {row[1] for row in resu.fetchall()}
            if "kind" not in cols_u:
                await conn.exec_driver_sql("ALTER TABLE llm_usage ADD COLUMN kind TEXT DEFAULT 'spot'")
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
        # futures_signals_cache new columns
        try:
            res4 = await conn.exec_driver_sql("PRAGMA table_info(futures_signals_cache)")
            cols_f = {row[1] for row in res4.fetchall()}
            if "oi_delta_h1" not in cols_f:
                await conn.exec_driver_sql(
                    "ALTER TABLE futures_signals_cache ADD COLUMN oi_delta_h1 FLOAT DEFAULT NULL"
                )
            if "oi_delta_h4" not in cols_f:
                await conn.exec_driver_sql(
                    "ALTER TABLE futures_signals_cache ADD COLUMN oi_delta_h4 FLOAT DEFAULT NULL"
                )
            if "basis_bp" not in cols_f:
                await conn.exec_driver_sql(
                    "ALTER TABLE futures_signals_cache ADD COLUMN basis_bp FLOAT DEFAULT NULL"
                )
            if "spread_bp" not in cols_f:
                await conn.exec_driver_sql(
                    "ALTER TABLE futures_signals_cache ADD COLUMN spread_bp FLOAT DEFAULT NULL"
                )
            if "depth10bp_bid" not in cols_f:
                await conn.exec_driver_sql(
                    "ALTER TABLE futures_signals_cache ADD COLUMN depth10bp_bid FLOAT DEFAULT NULL"
                )
            if "depth10bp_ask" not in cols_f:
                await conn.exec_driver_sql(
                    "ALTER TABLE futures_signals_cache ADD COLUMN depth10bp_ask FLOAT DEFAULT NULL"
                )
            if "ob_imbalance" not in cols_f:
                await conn.exec_driver_sql(
                    "ALTER TABLE futures_signals_cache ADD COLUMN ob_imbalance FLOAT DEFAULT NULL"
                )
        except Exception:
            pass

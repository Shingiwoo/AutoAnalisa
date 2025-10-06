from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from typing import Any
from .. import models
from ..config import settings


def _make_engine():
    url = settings.DATABASE_URL or settings.SQLITE_URL
    # For SQLite, set connect timeout to reduce "database is locked" errors under load
    kwargs: dict[str, Any] = {"echo": False, "future": True}
    if url.startswith("sqlite+"):
        kwargs["connect_args"] = {"timeout": 15}
    else:
        # For MySQL/Postgres, enable pre_ping and modest recycle to avoid stale connections
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 1800
    return create_async_engine(url, **kwargs)


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        # Aktifkan WAL & synchronous=NORMAL & busy_timeout untuk SQLite, abaikan jika gagal
        try:
            if engine.url.get_backend_name().startswith("sqlite"):
                await conn.execute(text("PRAGMA journal_mode=WAL"))
                await conn.execute(text("PRAGMA synchronous=NORMAL"))
                await conn.execute(text("PRAGMA busy_timeout=5000"))
        except Exception:
            pass
        await conn.run_sync(models.Base.metadata.create_all)
        # lightweight migrations for MySQL
        try:
            if engine.url.get_backend_name().startswith("mysql"):
                res = await conn.exec_driver_sql(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users'"
                )
                cols = {row[0] for row in res.fetchall()}
                if "approved" not in cols:
                    await conn.exec_driver_sql(
                        "ALTER TABLE users ADD COLUMN approved TINYINT(1) DEFAULT 1"
                    )
                if "blocked" not in cols:
                    await conn.exec_driver_sql(
                        "ALTER TABLE users ADD COLUMN blocked TINYINT(1) DEFAULT 0"
                    )
        except Exception:
            pass
        # lightweight migrations for SQLite
        try:
            # users: add approved & blocked flags for admin moderation
            resu = await conn.exec_driver_sql("PRAGMA table_info(users)")
            cols_users = {row[1] for row in resu.fetchall()}
            if "approved" not in cols_users:
                await conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN approved BOOLEAN DEFAULT 1"
                )
            if "blocked" not in cols_users:
                await conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN blocked BOOLEAN DEFAULT 0"
                )
        except Exception:
            pass
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
        # add trade_type to analyses and plans if missing
        try:
            res_a = await conn.exec_driver_sql("PRAGMA table_info(analyses)")
            cols_a = {row[1] for row in res_a.fetchall()}
            if "trade_type" not in cols_a:
                await conn.exec_driver_sql(
                    "ALTER TABLE analyses ADD COLUMN trade_type TEXT DEFAULT 'spot'"
                )
        except Exception:
            pass
        # ensure analyses unique index mencakup trade_type agar spot & futures terpisah
        try:
            idx_list = await conn.exec_driver_sql("PRAGMA index_list(analyses)")
            idx_rows = idx_list.fetchall()
            has_unique_on_ust = False
            for ir in idx_rows:
                try:
                    if int(ir[2]) != 1:
                        continue
                except Exception:
                    continue
                iname = ir[1]
                info = await conn.exec_driver_sql(f"PRAGMA index_info({iname})")
                cols_idx = [r[2] for r in info.fetchall()]
                if cols_idx == ["user_id", "symbol", "trade_type"]:
                    has_unique_on_ust = True
                    break
            if not has_unique_on_ust:
                await conn.exec_driver_sql(
                    "CREATE TABLE IF NOT EXISTS analyses__new (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, symbol TEXT, trade_type TEXT DEFAULT 'spot', version INTEGER DEFAULT 1, payload_json JSON, status TEXT DEFAULT 'active', created_at DATETIME, UNIQUE(user_id, symbol, trade_type))"
                )
                await conn.exec_driver_sql(
                    "INSERT INTO analyses__new (id, user_id, symbol, trade_type, version, payload_json, status, created_at) SELECT id, user_id, symbol, COALESCE(trade_type, 'spot'), version, payload_json, status, created_at FROM analyses"
                )
                await conn.exec_driver_sql("DROP TABLE analyses")
                await conn.exec_driver_sql("ALTER TABLE analyses__new RENAME TO analyses")
        except Exception:
            pass
        try:
            await conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_analyses_user_id ON analyses (user_id)")
            await conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_analyses_symbol ON analyses (symbol)")
            await conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_analyses_trade_type ON analyses (trade_type)")
        except Exception:
            pass
        try:
            res_p = await conn.exec_driver_sql("PRAGMA table_info(plans)")
            cols_p = {row[1] for row in res_p.fetchall()}
            if "trade_type" not in cols_p:
                await conn.exec_driver_sql(
                    "ALTER TABLE plans ADD COLUMN trade_type TEXT DEFAULT 'spot'"
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
            if "trade_type" not in cols_v:
                await conn.exec_driver_sql(
                    "ALTER TABLE llm_verifications ADD COLUMN trade_type TEXT DEFAULT 'spot'"
                )
            if "macro_snapshot" not in cols_v:
                await conn.exec_driver_sql(
                    "ALTER TABLE llm_verifications ADD COLUMN macro_snapshot JSON DEFAULT '{}'"
                )
            if "ui_contract" not in cols_v:
                await conn.exec_driver_sql(
                    "ALTER TABLE llm_verifications ADD COLUMN ui_contract JSON DEFAULT '{}'"
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
        # watchlist: add trade_type and enforce unique(user_id,symbol,trade_type)
        try:
            resw = await conn.exec_driver_sql("PRAGMA table_info(watchlist)")
            cols_w = {row[1] for row in resw.fetchall()}
            if "trade_type" not in cols_w:
                await conn.exec_driver_sql("ALTER TABLE watchlist ADD COLUMN trade_type TEXT DEFAULT 'spot'")
            # Recreate table to adjust unique constraint (SQLite limitation)
            # Detect whether unique index already includes trade_type
            idx_list = await conn.exec_driver_sql("PRAGMA index_list(watchlist)")
            idx_rows = idx_list.fetchall()
            has_unique_on_ust = False
            for ir in idx_rows:
                try:
                    if int(ir[2]) != 1:
                        continue
                except Exception:
                    continue
                iname = ir[1]
                info = await conn.exec_driver_sql(f"PRAGMA index_info({iname})")
                cols_idx = [r[2] for r in info.fetchall()]
                if cols_idx == ["user_id", "symbol", "trade_type"]:
                    has_unique_on_ust = True
                    break
            if not has_unique_on_ust:
                await conn.exec_driver_sql(
                    "CREATE TABLE IF NOT EXISTS watchlist__new (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, symbol TEXT, trade_type TEXT DEFAULT 'spot', created_at DATETIME, UNIQUE(user_id, symbol, trade_type))"
                )
                await conn.exec_driver_sql(
                    "INSERT OR IGNORE INTO watchlist__new (id, user_id, symbol, trade_type, created_at) SELECT id, user_id, symbol, COALESCE(trade_type, 'spot'), created_at FROM watchlist"
                )
                await conn.exec_driver_sql("DROP TABLE watchlist")
                await conn.exec_driver_sql("ALTER TABLE watchlist__new RENAME TO watchlist")
        except Exception:
            pass

from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Date,
    JSON,
    Text,
    Boolean,
    Float,
    UniqueConstraint,
    ForeignKey,
)
import datetime as dt


Base = declarative_base()


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    trade_type: Mapped[str] = mapped_column(String(16), default="spot")  # spot|futures
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))


# New tables for auth, analysis, usage, and settings
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid string
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="user")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    trade_type: Mapped[str] = mapped_column(String(16), default="spot")  # spot|futures
    version: Mapped[int] = mapped_column(Integer, default=1)
    # keep JSON to store structured plan
    payload_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="active")  # active|archived
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uniq_user_symbol"),)


class ApiUsage(Base):
    __tablename__ = "api_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    usd_cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    month_key: Mapped[str] = mapped_column(String, index=True)


class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    use_llm: Mapped[bool] = mapped_column(Boolean, default=True)
    registration_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_users: Mapped[int] = mapped_column(Integer, default=4)
    enable_fvg: Mapped[bool] = mapped_column(Boolean, default=False)
    enable_supply_demand: Mapped[bool] = mapped_column(Boolean, default=False)
    show_sessions_hint: Mapped[bool] = mapped_column(Boolean, default=True)
    default_weight_profile: Mapped[str] = mapped_column(String, default="DCA")
    llm_daily_limit_spot: Mapped[int] = mapped_column(Integer, default=40)
    llm_daily_limit_futures: Mapped[int] = mapped_column(Integer, default=40)
    # Indicator tuning parameters (admin configurable)
    fvg_use_bodies: Mapped[bool] = mapped_column(Boolean, default=False)
    fvg_fill_rule: Mapped[str] = mapped_column(String, default="any_touch")  # any_touch|50pct|full
    fvg_threshold_pct: Mapped[float] = mapped_column(Float, default=0.0)
    fvg_threshold_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    fvg_tf: Mapped[str] = mapped_column(String, default="15m")
    sd_max_base: Mapped[int] = mapped_column(Integer, default=3)
    sd_body_ratio: Mapped[float] = mapped_column(Float, default=0.33)
    sd_min_departure: Mapped[float] = mapped_column(Float, default=1.5)
    sd_mode: Mapped[str] = mapped_column(String, default="swing")  # swing|volume
    sd_vol_div: Mapped[int] = mapped_column(Integer, default=20)
    sd_vol_threshold_pct: Mapped[float] = mapped_column(Float, default=10.0)
    input_usd_per_1k: Mapped[float] = mapped_column(Float, default=0.005)
    output_usd_per_1k: Mapped[float] = mapped_column(Float, default=0.015)
    budget_monthly_usd: Mapped[float] = mapped_column(Float, default=20.0)
    auto_off_at_budget: Mapped[bool] = mapped_column(Boolean, default=True)
    budget_used_usd: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))
    # Futures settings (skeleton)
    enable_futures: Mapped[bool] = mapped_column(Boolean, default=False)
    futures_leverage_min: Mapped[int] = mapped_column(Integer, default=3)
    futures_leverage_max: Mapped[int] = mapped_column(Integer, default=10)
    futures_risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=0.5)
    futures_funding_threshold_bp: Mapped[float] = mapped_column(Float, default=3.0)  # 0.03%
    futures_funding_avoid_minutes: Mapped[int] = mapped_column(Integer, default=10)
    futures_liq_buffer_k_atr15m: Mapped[float] = mapped_column(Float, default=0.5)
    futures_default_weight_profile: Mapped[str] = mapped_column(String, default="DCA")
    futures_funding_alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    futures_funding_alert_window_min: Mapped[int] = mapped_column(Integer, default=30)


class Watchlist(Base):
    __tablename__ = "watchlist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uniq_user_symbol_watch"),)


class PasswordChangeRequest(Base):
    __tablename__ = "pwd_change_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    new_hash: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|rejected
    requested_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, default=None)
    processed_by: Mapped[str | None] = mapped_column(String, default=None)


class MacroDaily(Base):
    __tablename__ = "macro_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date_utc: Mapped[str] = mapped_column(String, index=True)  # YYYY-MM-DD (UTC)
    narrative: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text, default="")
    sections: Mapped[list] = mapped_column(JSON, default=list)
    slot: Mapped[str] = mapped_column(String, default="pagi")  # pagi|malam
    last_run_status: Mapped[str] = mapped_column(String, default="ok")  # ok|skip|error
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))


# Verification records from LLM for each analysis snapshot
class LLMVerification(Base):
    __tablename__ = "llm_verifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String, default="gpt-5-chat-latest")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String, default="confirm")  # confirm|tweak|warning|reject
    summary: Mapped[str] = mapped_column(Text, default="")
    suggestions: Mapped[dict] = mapped_column(JSON, default={})  # {entries:[], tp:[], invalid:..., notes:[]}
    fundamentals: Mapped[dict] = mapped_column(JSON, default={})  # optional bullets for 24–48h
    spot2_json: Mapped[dict] = mapped_column(JSON, default={})
    futures_json: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))
    cached: Mapped[bool] = mapped_column(Boolean, default=False)


# Aggregated per-day usage per user for LLM calls and token costs
class LLMUsage(Base):
    __tablename__ = "llm_usage"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid string
    user_id: Mapped[str] = mapped_column(String, index=True)
    day: Mapped[dt.date] = mapped_column(Date, index=True)  # UTC date
    month: Mapped[str] = mapped_column(String, index=True)   # YYYY-MM
    model: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="spot")  # spot|futures
    calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, default=None)


# Futures metadata and signals cache (skeleton for Futures module)
class FuturesMeta(Base):
    __tablename__ = "futures_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    contract: Mapped[str] = mapped_column(String, default="PERP")  # PERP|USDT-M
    leverage_min: Mapped[int] = mapped_column(Integer, default=1)
    leverage_max: Mapped[int] = mapped_column(Integer, default=20)
    maint_margin_tbl: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class FuturesSignalsCache(Base):
    __tablename__ = "futures_signals_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    funding_now: Mapped[float | None] = mapped_column(Float, default=None)
    funding_next: Mapped[float | None] = mapped_column(Float, default=None)
    next_funding_time: Mapped[str | None] = mapped_column(String, default=None)  # ISO8601
    oi_now: Mapped[float | None] = mapped_column(Float, default=None)
    oi_d1: Mapped[float | None] = mapped_column(Float, default=None)
    oi_delta_h1: Mapped[float | None] = mapped_column(Float, default=None)
    oi_delta_h4: Mapped[float | None] = mapped_column(Float, default=None)
    lsr_accounts: Mapped[float | None] = mapped_column(Float, default=None)
    lsr_positions: Mapped[float | None] = mapped_column(Float, default=None)
    basis_now: Mapped[float | None] = mapped_column(Float, default=None)
    basis_bp: Mapped[float | None] = mapped_column(Float, default=None)
    taker_delta_m5: Mapped[float | None] = mapped_column(Float, default=None)
    taker_delta_m15: Mapped[float | None] = mapped_column(Float, default=None)
    taker_delta_h1: Mapped[float | None] = mapped_column(Float, default=None)
    spread_bp: Mapped[float | None] = mapped_column(Float, default=None)
    depth10bp_bid: Mapped[float | None] = mapped_column(Float, default=None)
    depth10bp_ask: Mapped[float | None] = mapped_column(Float, default=None)
    ob_imbalance: Mapped[float | None] = mapped_column(Float, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

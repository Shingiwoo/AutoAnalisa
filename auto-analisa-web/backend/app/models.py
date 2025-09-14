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
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


# New tables for auth, analysis, usage, and settings
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid string
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="user")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    # keep JSON to store structured plan
    payload_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="active")  # active|archived
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
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
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class Watchlist(Base):
    __tablename__ = "watchlist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uniq_user_symbol_watch"),)


class PasswordChangeRequest(Base):
    __tablename__ = "pwd_change_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    new_hash: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|rejected
    requested_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, default=None)
    processed_by: Mapped[str | None] = mapped_column(String, default=None)


class MacroDaily(Base):
    __tablename__ = "macro_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date_utc: Mapped[str] = mapped_column(String, index=True)  # YYYY-MM-DD (UTC)
    narrative: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text, default="")
    sections: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


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
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)


# Aggregated per-day usage per user for LLM calls and token costs
class LLMUsage(Base):
    __tablename__ = "llm_usage"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid string
    user_id: Mapped[str] = mapped_column(String, index=True)
    day: Mapped[dt.date] = mapped_column(Date, index=True)  # UTC date
    month: Mapped[str] = mapped_column(String, index=True)   # YYYY-MM
    model: Mapped[str] = mapped_column(String)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, default=None)

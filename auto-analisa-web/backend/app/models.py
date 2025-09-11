from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import (
    Integer,
    String,
    DateTime,
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
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

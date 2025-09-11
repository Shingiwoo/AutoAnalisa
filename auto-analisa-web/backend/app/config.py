from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App & storage
    APP_ENV: str = "local"
    SQLITE_URL: str = "sqlite+aiosqlite:///./app.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth & security
    REQUIRE_LOGIN: bool = True
    JWT_SECRET: str = "dev-secret"
    # Support both names; prefer JWT_EXPIRE_MIN
    JWT_EXPIRE_MIN: int = 43200
    JWT_EXPIRE_MINUTES: int = 43200

    # Features
    BINANCE_SANDBOX: bool = False
    USE_LLM: bool = False

    # CORS
    CORS_ORIGINS: str = "*"  # comma-separated. Use * for local


settings = Settings()

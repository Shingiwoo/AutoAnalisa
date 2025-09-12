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

    # LLM daily limit and budget (env patch)
    LLM_DAILY_LIMIT: int = 40
    # Alias for monthly budget if not using DB settings
    LLM_BUDGET_USD: float = 20.0
    # Pricing per 1,000,000 tokens (default Flex)
    LLM_PRICE_INPUT_USD_PER_MTOK: float = 0.625
    LLM_PRICE_OUTPUT_USD_PER_MTOK: float = 5.0

    # CORS
    CORS_ORIGINS: str = "*"  # comma-separated. Use * for local


settings = Settings()

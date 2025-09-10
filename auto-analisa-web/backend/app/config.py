from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "local"
    SECRET_KEY: str = "dev-secret"
    SQLITE_URL: str = "sqlite+aiosqlite:///./app.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    BINANCE_SANDBOX: bool = False
    USE_LLM: bool = False


settings = Settings()


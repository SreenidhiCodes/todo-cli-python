from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Environment based application configuration."""

    app_name = os.getenv("APP_NAME", "TaskFlow API")
    api_prefix = "/api/v1"
    database_url = os.getenv("DATABASE_URL", "sqlite:///./taskflow.db")
    secret_key = os.getenv("SECRET_KEY", "development-only-change-this-secret")
    access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
    environment = os.getenv("ENVIRONMENT", "development").lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()

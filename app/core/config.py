"""Application settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///./rasa_gate.db"

    # Rasa server
    rasa_url: str = "http://localhost:5005"
    rasa_model_path: str = "./models"

    # API key auth — set in .env to enable, leave blank to disable
    auth_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

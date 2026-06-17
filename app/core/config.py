# app/core/config.py
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

    # Shared volume where YAML files and trained models are written
    rasa_model_path: str = "./models"

    # API key auth — set this in .env to enable, leave blank to disable
    auth_token: str | None = None

    @property
    def rasa_server_url(self) -> str:
        """Alias so existing service code keeps working without changes."""
        return self.rasa_url

    @property
    def rasa_shared_volume(self) -> str:
        """Alias so training.py keeps working without changes."""
        return self.rasa_model_path

    @property
    def api_key(self) -> str | None:
        """Alias so auth middleware keeps working without changes."""
        return self.auth_token


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
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

    # Rasa training config. Every training payload needs these — without
    # `recipe` and `assistant_id`, Rasa 3.x rejects the training request.
    # Leaving `pipeline`/`policies` empty tells Rasa to use its built-in
    # defaults (same as commenting them out in a normal config.yml).
    rasa_recipe: str = "default.v1"
    rasa_assistant_id: str = "rasa-gate-bot"
    rasa_language: str = "en"

    # Startup behavior: wait for Rasa to be reachable and preload the last
    # trained model. Disable for local dev / tests where Rasa isn't running.
    rasa_startup_wait: bool = True
    rasa_startup_max_retries: int = 15
    rasa_startup_retry_delay: float = 2.0

    # API key auth — set in .env to enable, leave blank to disable
    auth_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

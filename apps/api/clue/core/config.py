"""Application settings, read from environment / .env at the repo root."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_mode: str = "self_host"
    web_port: int = 3000
    api_port: int = 8000
    site_url: str = "http://localhost:3000"
    openrouter_api_key: str = ""
    model_fast: str = ""
    model_smart: str = ""
    ollama_url: str = ""
    storage_path: str = "./storage"
    admin_email: str = "admin@clue.local"
    feature_url_import: bool = False
    database_url: str = ""

    @property
    def storage_dir(self) -> Path:
        p = Path(self.storage_path)
        p = p if p.is_absolute() else ROOT / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.storage_dir / 'clue.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()

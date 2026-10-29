from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:////data/app.db"
    postgres_password: str = "copilot-local"
    redis_url: str = "redis://redis:6379/0"
    prometheus_url: str = "http://prometheus:9090"
    prometheus_token: str = ""
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    model_cache: Path = Path("/data/models")
    upload_dir: Path = Path("/data/uploads")
    session_secure: bool = False
    demo_mode: bool = True
    demo_exporter_url: str = "http://demo-exporter:9101"

    @model_validator(mode="after")
    def resolve_database_url(self):
        self.database_url = "sqlite:////data/app.db"
        return self


@lru_cache
def settings() -> Settings:
    return Settings()

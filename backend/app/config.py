from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://copilot:copilot-local@db:5432/copilot"
    redis_url: str = "redis://redis:6379/0"
    prometheus_url: str = "http://prometheus:9090"
    prometheus_token: str = ""
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    model_cache: Path = Path("/data/models")
    upload_dir: Path = Path("/data/uploads")
    operator_password: str = "copilot-demo"
    session_secure: bool = False
    demo_mode: bool = True
    demo_exporter_url: str = "http://demo-exporter:9101"


@lru_cache
def settings() -> Settings:
    return Settings()

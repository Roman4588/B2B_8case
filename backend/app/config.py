from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = ""
    postgres_password: str = "copilot-local"
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

    @model_validator(mode="after")
    def resolve_database_url(self):
        if not self.database_url:
            self.database_url = URL.create(
                "postgresql+psycopg",
                username="copilot",
                password=self.postgres_password,
                host="db",
                port=5432,
                database="copilot",
            ).render_as_string(hide_password=False)
        return self


@lru_cache
def settings() -> Settings:
    return Settings()

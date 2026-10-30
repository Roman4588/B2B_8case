from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    session_secure: bool = False
    demo_mode: bool = True
    demo_exporter_url: str = "http://demo-exporter:9101"
    search_in_worker: bool = False
    embedding_threads: int = Field(default=2, ge=1, le=8)
    embedding_batch_size: int = Field(default=16, ge=1, le=16)
    embedding_memory_arena: bool = True

    @model_validator(mode="after")
    def resolve_database_url(self):
        if not self.database_url:
            password = quote_plus(self.postgres_password)
            self.database_url = f"postgresql+psycopg://copilot:{password}@db:5432/copilot"
        return self


@lru_cache
def settings() -> Settings:
    return Settings()

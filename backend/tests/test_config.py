from app.config import Settings


def test_postgres_default_and_escaped_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = Settings(_env_file=None, postgres_password="p@ss/word")
    assert config.database_url == "postgresql+psycopg://copilot:p%40ss%2Fword@db:5432/copilot"


def test_explicit_database_is_not_overridden():
    config = Settings(_env_file=None, database_url="postgresql+psycopg://cloud/db")
    assert config.database_url == "postgresql+psycopg://cloud/db"

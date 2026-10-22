from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings


@lru_cache
def engine():
    return create_engine(settings().database_url, pool_pre_ping=True)


def session_factory():
    return sessionmaker(engine(), expire_on_commit=False)


def get_db():
    with session_factory()() as session:
        yield session

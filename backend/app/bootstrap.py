import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.db import session_factory
from app.models import Operator, Runbook


def bootstrap():
    root = Path(__file__).resolve().parents[1]
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    with session_factory()() as db:
        if db.scalar(select(Operator.id).limit(1)) is None:
            db.add(Operator(name="Дежурный инженер", password_hash=hash_password(settings().operator_password)))
        records = json.loads((Path(__file__).parent / "seed" / "runbooks.json").read_text(encoding="utf-8"))
        for index, record in enumerate(records):
            key = f"seed:{index}"
            if db.scalar(select(Runbook.id).where(Runbook.content_key == key)) is None:
                db.add(Runbook(**record, content_key=key, source="Демонстрационный регламент · v1"))
        db.commit()
    print("Database migrated; operator and runbooks initialized. Model indexing runs in worker.")


if __name__ == "__main__":
    bootstrap()

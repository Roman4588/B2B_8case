import hashlib

import pytest
from app.models import Base, Operator, Runbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def legacy(tmp_path):
    path = tmp_path / "app.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Operator(id="old-user", name="Existing owner", email="owner@example.org", role="admin",
                        password_hash="existing-hash-must-be-preserved"))
        db.add(Runbook(id="old-book", title="Существующая инструкция", condition="Очередь стоит",
                       steps=["Проверить обработчик"], content_key="seed:0", status="ready"))
        db.commit()
    engine.dispose()
    return path


def test_legacy_data_is_preserved_and_import_is_idempotent(tmp_path):
    from app.sqlite_migration import migrate_sqlite

    source = legacy(tmp_path)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    target = create_engine("sqlite://")
    Base.metadata.create_all(target)
    assert migrate_sqlite(source, target)["status"] == "imported"
    with Session(target) as db:
        assert db.get(Operator, "old-user").password_hash == "existing-hash-must-be-preserved"
        book = db.get(Runbook, "old-book")
        assert book.title == "Существующая инструкция" and book.steps == ["Проверить обработчик"]
        assert book.status == "queued"
    assert migrate_sqlite(source, target)["status"] == "already_imported"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original


def test_import_refuses_to_merge_over_existing_target_data(tmp_path):
    from app.sqlite_migration import migrate_sqlite

    source = legacy(tmp_path)
    target = create_engine("sqlite://")
    Base.metadata.create_all(target)
    with Session(target) as db:
        db.add(Operator(id="new-owner", email="new@example.org", password_hash="keep-this"))
        db.commit()
    with pytest.raises(RuntimeError, match="nonempty"):
        migrate_sqlite(source, target)
    with Session(target) as db:
        assert db.get(Operator, "new-owner").password_hash == "keep-this"
        assert db.get(Operator, "old-user") is None

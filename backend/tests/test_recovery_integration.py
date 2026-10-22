import os
from datetime import timedelta
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("INTEGRATION"), reason="Needs PostgreSQL"),
]


@pytest.fixture
def factory():
    from app.config import settings
    from app.models import Base

    name = "case8_test_" + uuid4().hex
    admin = create_engine(settings().database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(make_url(settings().database_url).set(database=name))
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION vector"))
        Base.metadata.create_all(connection)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_new_index_refreshes_previously_ready_incidents(factory):
    from app.knowledge import index_runbook
    from app.models import Incident, Runbook

    with factory() as db:
        incident = Incident(
            source="test",
            external_id="new-book",
            title="Disk full",
            lifecycle="firing",
            recommendation_status="ready",
            recommendations=[],
        )
        book = Runbook(
            title="Disk full", condition="Disk full, на диске нет места", steps=["Проверить df -h"]
        )
        db.add_all([incident, book])
        db.commit()
        index_runbook(db, book.id)
        db.refresh(incident)
        assert incident.recommendation_status == "pending"


def test_stale_import_recovery_is_committed_without_other_work(factory, monkeypatch):
    from app import tasks
    from app.models import ImportJob, utcnow

    with factory() as db:
        job = ImportJob(
            filename="abandoned.txt",
            path="/tmp/abandoned.txt",
            status="running",
            updated_at=utcnow() - timedelta(minutes=20),
        )
        db.add(job)
        db.commit()
        job_id = job.id
    monkeypatch.setattr(tasks, "session_factory", lambda: factory)
    tasks.maintenance.run()
    with factory() as db:
        assert db.get(ImportJob, job_id).status == "queued"


def test_edit_during_index_publication_cannot_mark_old_vectors_ready(factory):
    from app.knowledge import index_runbook
    from app.models import Runbook

    with factory() as db:
        book = Runbook(title="Disk full", condition="Disk full, мало места", steps=["Проверить df -h"])
        db.add(book)
        db.commit()
        book_id = book.id
    done, started = Event(), Event()
    failures = []

    def writer():
        try:
            with factory() as other:
                row = other.scalar(select(Runbook).where(Runbook.id == book_id).with_for_update())
                row.condition, row.revision, row.status = "New version about network packets", 2, "queued"
                other.commit()
        except Exception as exc:
            failures.append(str(exc))
        finally:
            done.set()

    thread = Thread(target=writer)
    with factory() as db:

        def during_delete(conn, cursor, statement, params, context, executemany):
            if statement.upper().startswith("DELETE FROM CHUNKS") and not started.is_set():
                started.set()
                thread.start()
                done.wait(1)

        event.listen(db.bind, "before_cursor_execute", during_delete)
        try:
            index_runbook(db, book_id)
        finally:
            event.remove(db.bind, "before_cursor_execute", during_delete)
    thread.join(timeout=5)
    assert started.is_set() and done.is_set() and not failures
    with factory() as db:
        row = db.get(Runbook, book_id)
        assert row.revision == 2
        assert row.status == "queued"

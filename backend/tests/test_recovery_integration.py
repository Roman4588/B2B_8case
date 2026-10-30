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


def test_maintenance_lock_survives_commits_and_is_released(factory):
    from app.tasks import maintenance_lock

    with factory() as db:
        with maintenance_lock(db) as acquired:
            assert acquired
            db.commit()
            with factory() as other:
                assert not other.scalar(text("SELECT pg_try_advisory_xact_lock(8009)"))
        with factory() as other:
            assert other.scalar(text("SELECT pg_try_advisory_xact_lock(8009)"))


def test_slow_live_import_is_not_reclaimed_or_processed_twice(factory, monkeypatch, tmp_path):
    from app import tasks
    from app.models import ImportJob, Runbook, utcnow

    path = tmp_path / "slow.txt"
    path.write_text("If disk full -> Check disk space", encoding="utf-8")
    with factory() as db:
        job = ImportJob(filename=path.name, path=str(path))
        db.add(job)
        db.commit()
        job_id = job.id
    monkeypatch.setattr(tasks, "session_factory", lambda: factory)
    monkeypatch.setattr(tasks.import_file, "delay", lambda job_id: None)
    calls = []

    def slow_extract(content, extension):
        calls.append(1)
        if len(calls) == 1:
            with factory() as other:
                other.get(ImportJob, job_id).updated_at = utcnow() - timedelta(minutes=16)
                other.commit()
            tasks.maintenance.run()
            with factory() as other:
                tasks.process_import(other, job_id)
            assert len(calls) == 1, "The live import was started a second time"
        return content.decode()

    def index_without_model(db, book_id):
        db.get(Runbook, book_id).status = "ready"
        db.commit()

    monkeypatch.setattr(tasks, "extract", slow_extract)
    monkeypatch.setattr(tasks, "index_runbook", index_without_model)
    with factory() as db:
        tasks.process_import(db, job_id)
    with factory() as db:
        assert db.get(ImportJob, job_id).status == "succeeded"
        assert len(calls) == 1
        assert len(db.scalars(select(Runbook)).all()) == 1


@pytest.mark.parametrize("concurrent_change", ["publish", "invalidate"])
def test_poll_invalidates_concurrent_recommendations_in_postgres(factory, monkeypatch, concurrent_change):
    from app import monitoring
    from app.models import Incident
    from app.recommendations import invalidate_recommendations, refresh_recommendations

    alert = {
        "state": "firing",
        "labels": {"alertname": "HostFailure"},
        "annotations": {"summary": "Disk full"},
    }
    with factory() as db:
        incident_id = monitoring.ingest_alerts(db, [alert], "prometheus")[0]
        original = monitoring.classify
        generations = []

        def interleave(value):
            with factory() as other:
                if concurrent_change == "publish":
                    refresh_recommendations(other, incident_id, lambda session, query: [{"title": query}])
                else:
                    invalidate_recommendations(other)
                    other.commit()
                generations.append(other.get(Incident, incident_id).recommendation_generation)
            return original(value)

        monkeypatch.setattr(monitoring, "classify", interleave)
        alert["annotations"]["summary"] = "Network unreachable"
        monitoring.ingest_alerts(db, [alert], "prometheus")
    with factory() as check:
        item = check.get(Incident, incident_id)
        assert item.recommendation_status == "pending" and item.recommendations == []
        assert item.recommendation_generation > generations[0]


def test_postgres_upgrade_preserves_existing_decisions(factory):
    import importlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    from app.models import AuditEntry, Incident

    with factory() as db:
        incident = Incident(
            id="legacy", source="test", external_id="legacy", title="Old incident", handling="accepted"
        )
        db.add(incident)
        db.add(AuditEntry(actor="Engineer", action="accept", incident_id="legacy", comment="Old decision"))
        db.commit()
        engine = db.get_bind()
    with engine.begin() as connection:
        # Reproduce the populated schema before recommendation generations existed.
        connection.execute(text("ALTER TABLE incidents DROP COLUMN recommendation_generation"))
        migration = importlib.import_module("migrations.versions.0002_recommendation_generation")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
    with factory() as db:
        item = db.get(Incident, "legacy")
        assert item.handling == "accepted" and item.recommendation_generation == 0
        decision = db.scalar(select(AuditEntry).where(AuditEntry.incident_id == "legacy"))
        assert decision.comment == "Old decision" and decision.actor == "Engineer"

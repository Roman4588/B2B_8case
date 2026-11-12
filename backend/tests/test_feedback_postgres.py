# ruff: noqa: F811
"""Run only with INTEGRATION=1; factory creates a disposable database per test."""

import importlib
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from test_recovery_integration import factory  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("INTEGRATION"), reason="Needs isolated PostgreSQL"),
]


def test_concurrent_corrections_and_feedback_are_unique(factory):
    from app.feedback import save_correction, save_feedback
    from app.models import (
        AuditEntry,
        ClassificationCorrection,
        Incident,
        Operator,
        RecommendationFeedback,
        Runbook,
    )

    with factory() as db:
        operator = Operator(name="Engineer", email="test@example.org", password_hash="unused")
        db.add_all(
            [
                operator,
                Runbook(id="book", title="Disk", condition="disk", steps=["check"]),
                Incident(
                    id="event",
                    source="test",
                    external_id="1",
                    title="Disk",
                    recommendation_status="ready",
                    recommendation_generation=2,
                    recommendations=[
                        {
                            "id": "book",
                            "revision": 1,
                            "title": "Disk",
                            "condition": "disk",
                            "steps": ["check"],
                        }
                    ],
                ),
            ]
        )
        db.commit()
        operator_id = operator.id
    barrier = Barrier(2)

    def write_correction(_):
        with factory() as db:
            operator = db.get(Operator, operator_id)
            barrier.wait(timeout=10)
            save_correction(
                db,
                "event",
                operator,
                {"severity": "info", "category": "network", "priority": "P2", "comment": "same"},
            )

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(write_correction, range(2)))
    barrier = Barrier(2)

    def write_feedback(_):
        with factory() as db:
            operator = db.get(Operator, operator_id)
            barrier.wait(timeout=10)
            save_feedback(db, "event", "book", operator, True, 1, 2)

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(write_feedback, range(2)))
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ClassificationCorrection)) == 1
        assert db.scalar(select(func.count()).select_from(RecommendationFeedback)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEntry)) == 2
        correction = db.scalar(select(ClassificationCorrection))
        db.add(
            ClassificationCorrection(
                incident_id="event",
                operator_id=operator_id,
                actor="Engineer",
                severity="info",
                category="network",
                priority="P2",
                input_snapshot=correction.input_snapshot,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        feedback = db.scalar(select(RecommendationFeedback))
        db.add(
            RecommendationFeedback(
                incident_id="event",
                operator_id=operator_id,
                actor="Engineer",
                runbook_id="book",
                revision=1,
                generation=2,
                helpful=False,
                recommendation_snapshot=feedback.recommendation_snapshot,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_upgrade_preserves_existing_rows_on_postgresql(factory):
    from app.models import ClassificationCorrection, RecommendationFeedback

    with factory.kw["bind"].begin() as connection:
        # Start from the actual 0003 schema, leaving an existing incident and audit.
        RecommendationFeedback.__table__.drop(connection)
        ClassificationCorrection.__table__.drop(connection)
        connection.execute(text("ALTER TABLE audit DROP COLUMN details"))
        connection.execute(text("ALTER TABLE audit DROP COLUMN operator_id"))
        from migrations.initial_schema import Base as InitialBase

        incident = InitialBase.metadata.tables["incidents"]
        connection.execute(
            incident.insert().values(
                id="old", source="test", external_id="old", title="Old", handling="accepted"
            )
        )
        connection.execute(
            text(
                "INSERT INTO audit (id,actor,action,comment,created_at) VALUES ('old','Engineer','accept','preserve',CURRENT_TIMESTAMP)"
            )
        )
        migration = importlib.import_module("migrations.versions.0004_engineer_feedback")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(text("SELECT title, handling FROM incidents WHERE id='old'")).one() == (
            "Old",
            "accepted",
        )
        assert connection.execute(text("SELECT comment FROM audit WHERE id='old'")).scalar_one() == "preserve"
        assert connection.execute(text("SELECT count(*) FROM classification_corrections")).scalar_one() == 0


def test_feedback_waiting_for_invalidation_rejects_stale_generation(factory):
    from threading import Event

    from app.feedback import save_feedback
    from app.models import Incident, Operator, RecommendationFeedback, Runbook
    from fastapi import HTTPException
    from sqlalchemy import event

    with factory() as db:
        operator = Operator(name="Engineer", email="test@example.org", password_hash="unused")
        db.add_all(
            [
                operator,
                Runbook(id="book", title="Disk", condition="Disk", steps=["Check"]),
                Incident(
                    id="event",
                    source="test",
                    external_id="1",
                    title="Disk",
                    recommendation_status="ready",
                    recommendation_generation=2,
                    recommendations=[{"id": "book", "revision": 1, "title": "Disk"}],
                ),
            ]
        )
        db.commit()
        operator_id = operator.id
    attempted = Event()

    def before_select(connection, cursor, statement, params, context, many):
        if "FOR UPDATE" in statement:
            attempted.set()

    def vote():
        with factory() as db:
            with pytest.raises(HTTPException) as error:
                save_feedback(db, "event", "book", db.get(Operator, operator_id), True, 1, 2)
            assert error.value.status_code == 409

    with factory() as db, ThreadPoolExecutor(1) as pool:
        incident = db.scalar(select(Incident).where(Incident.id == "event").with_for_update())
        incident.recommendation_status = "pending"
        incident.recommendation_generation = 3
        incident.recommendations = []
        db.flush()
        event.listen(factory.kw["bind"], "before_cursor_execute", before_select)
        try:
            future = pool.submit(vote)
            assert attempted.wait(10)
            db.commit()
            future.result(timeout=15)
        finally:
            event.remove(factory.kw["bind"], "before_cursor_execute", before_select)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(RecommendationFeedback)) == 0


def test_deleted_runbook_does_not_delete_or_block_historical_feedback(factory):
    from app.feedback import save_feedback
    from app.models import Incident, Operator, RecommendationFeedback, Runbook

    with factory() as db:
        operator = Operator(name="Engineer", email="test@example.org", password_hash="unused")
        db.add_all(
            [
                operator,
                Runbook(id="book", title="Disk", condition="Original condition", steps=["Check"]),
                Incident(
                    id="event",
                    source="test",
                    external_id="1",
                    title="Disk",
                    recommendation_status="ready",
                    recommendation_generation=2,
                    recommendations=[
                        {
                            "id": "book",
                            "revision": 1,
                            "title": "Disk",
                            "condition": "Original condition",
                            "steps": ["Check"],
                        }
                    ],
                ),
            ]
        )
        db.commit()
        save_feedback(db, "event", "book", operator, True, 1, 2)
        db.delete(db.get(Runbook, "book"))
        db.commit()
        feedback = db.scalar(select(RecommendationFeedback))
        assert feedback.runbook_id == "book" and feedback.helpful
        assert feedback.recommendation_snapshot["condition"] == "Original condition"

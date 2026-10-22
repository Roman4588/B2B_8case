import pytest
from app.models import AuditEntry, Base, Incident
from app.monitoring import ingest_alerts
from app.operations import manual_action
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def alert():
    return {"labels": {"alertname": "PostgresDown", "instance": "db-01", "severity": "critical"},
            "annotations": {"summary": "PostgreSQL primary is down", "description": "No connections"},
            "state": "firing", "activeAt": "2026-10-22T10:00:00Z", "value": "1"}


def test_repeated_polls_do_not_duplicate_and_empty_success_resolves(db):
    ingest_alerts(db, [alert()], "prometheus")
    ingest_alerts(db, [alert()], "prometheus")
    records = db.scalars(select(Incident)).all()
    assert len(records) == 1
    assert records[0].severity == "critical"
    ingest_alerts(db, [], "prometheus")
    assert records[0].lifecycle == "resolved"


def test_pending_is_not_a_firing_incident(db):
    item = alert()
    item["state"] = "pending"
    ingest_alerts(db, [item], "prometheus")
    assert db.scalar(select(Incident)) is None


def test_confirmation_records_only_manual_workflow(db):
    ingest_alerts(db, [alert()], "prometheus")
    incident = db.scalar(select(Incident))
    manual_action(db, incident.id, "accept", "Инженер", "Проверю первичный узел")
    manual_action(db, incident.id, "accept", "Инженер", "повтор")
    assert incident.handling == "accepted"
    assert len(db.scalars(select(AuditEntry)).all()) == 1
    manual_action(db, incident.id, "complete", "Инженер", "Выполнено через консоль вручную")
    assert incident.handling == "completed"
    assert incident.lifecycle == "firing"
    with pytest.raises(ValueError):
        manual_action(db, incident.id, "accept", "Инженер", "")

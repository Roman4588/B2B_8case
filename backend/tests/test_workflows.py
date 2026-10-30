from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import AuditEntry, Base, Incident
from app.monitoring import ingest_alerts
from app.operations import manual_action


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def alert():
    return {
        "labels": {"alertname": "PostgresDown", "instance": "db-01", "severity": "critical"},
        "annotations": {"summary": "PostgreSQL primary is down", "description": "No connections"},
        "state": "firing",
        "activeAt": "2026-10-22T10:00:00Z",
        "value": "1",
    }


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


def test_recurring_outage_keeps_previous_episode_and_audit(db):
    first = alert()
    ingest_alerts(db, [first], "prometheus")
    old = db.scalar(select(Incident))
    manual_action(db, old.id, "accept", "Инженер", "Первая авария")
    ingest_alerts(db, [], "prometheus")
    recovered = old.recovered_at
    again = alert()
    again["activeAt"] = "2026-10-22T11:00:00Z"
    ingest_alerts(db, [again], "prometheus")
    ingest_alerts(db, [again], "prometheus")
    rows = db.scalars(select(Incident)).all()
    assert len(rows) == 2
    assert old.lifecycle == "resolved"
    assert old.handling == "accepted"
    assert old.recovered_at == recovered
    new = next(row for row in rows if row.id != old.id)
    assert new.handling == "new" and new.lifecycle == "firing"
    assert new.first_seen.replace(tzinfo=UTC) == datetime(2026, 10, 22, 11, tzinfo=UTC)
    assert db.scalar(select(AuditEntry)).incident_id == old.id


def test_active_at_change_detects_recurrence_between_polls(db):
    first = alert()
    ingest_alerts(db, [first], "prometheus")
    first["activeAt"] = "2026-10-22T12:00:00Z"
    ingest_alerts(db, [first], "prometheus")
    assert len(db.scalars(select(Incident)).all()) == 2
    assert len(db.scalars(select(Incident).where(Incident.lifecycle == "firing")).all()) == 1


def test_changed_event_discards_old_recommendations(db):
    first = alert()
    ingest_alerts(db, [first], "prometheus")
    item = db.scalar(select(Incident))
    generation = item.recommendation_generation
    item.recommendations, item.recommendation_status = [{"title": "Old advice"}], "ready"
    db.commit()
    first["annotations"]["description"] = "New problem"
    ingest_alerts(db, [first], "prometheus")
    assert item.recommendations == []
    assert item.recommendation_status == "pending"
    assert item.recommendation_generation > generation


@pytest.mark.parametrize("concurrent_change", ["publish", "invalidate"])
def test_changed_event_invalidates_concurrent_search(db, monkeypatch, concurrent_change):
    from app import monitoring
    from app.recommendations import invalidate_recommendations, refresh_recommendations

    first = alert()
    ingest_alerts(db, [first], "prometheus")
    incident_id = db.scalar(select(Incident.id))
    original = monitoring.classify
    generations = []

    def interleave(event):
        with Session(db.bind, expire_on_commit=False) as other:
            if concurrent_change == "publish":
                refresh_recommendations(other, incident_id, lambda session, query: [{"title": query}])
            else:
                invalidate_recommendations(other)
                other.commit()
            generations.append(other.get(Incident, incident_id).recommendation_generation)
        return original(event)

    monkeypatch.setattr(monitoring, "classify", interleave)
    first["annotations"]["description"] = "A different failure now"
    ingest_alerts(db, [first], "prometheus")
    with Session(db.bind) as check:
        item = check.get(Incident, incident_id)
        assert item.recommendation_status == "pending"
        assert item.recommendations == []
        assert item.recommendation_generation > generations[0]

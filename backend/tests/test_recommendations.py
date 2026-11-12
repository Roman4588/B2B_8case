import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, Incident
from app.recommendations import invalidate_recommendations, refresh_recommendations


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Incident(id="event", source="test", external_id="1", title="Disk full"))
        session.commit()
        yield session


def test_obsolete_search_does_not_overwrite_new_request(db):
    def edit_during_search(session, query):
        invalidate_recommendations(session)
        session.commit()
        return [{"title": "Obsolete"}]

    refresh_recommendations(db, "event", edit_during_search)
    item = db.get(Incident, "event", populate_existing=True)
    assert item.recommendations == []
    assert item.recommendation_status == "pending"


def test_search_failure_is_visible_and_can_be_retried(db):
    def fail(session, query):
        raise RuntimeError("Model unavailable")

    refresh_recommendations(db, "event", fail)
    item = db.get(Incident, "event", populate_existing=True)
    assert item.recommendation_status == "failed"
    invalidate_recommendations(db)
    db.commit()
    refresh_recommendations(db, "event", lambda session, query: [{"title": "Check disk"}])
    assert db.scalar(select(Incident)).recommendations == [{"title": "Check disk"}]


def test_recovered_event_does_not_receive_late_advice(db):
    def recover(session, query):
        item = session.get(Incident, "event")
        item.lifecycle = "resolved"
        session.commit()
        return [{"title": "Late advice"}]

    refresh_recommendations(db, "event", recover)
    assert db.get(Incident, "event", populate_existing=True).recommendations == []


@pytest.mark.parametrize(
    "title,description",
    [
        ("Плановая проверка приложения завершена", "Health check completed."),
        ("Health check completed successfully", "Application is healthy."),
    ],
)
def test_successful_check_does_not_search_for_recovery(db, title, description):
    item = db.get(Incident, "event")
    item.title, item.description = title, description
    item.severity, item.priority, item.needs_review = "info", "P4", False
    db.commit()

    def forbidden(*args):
        pytest.fail("Successful checks must not invoke semantic recovery search")

    refresh_recommendations(db, "event", forbidden)
    assert db.get(Incident, "event").recommendation_status == "not_required"
    assert db.get(Incident, "event").recommendations == []


@pytest.mark.parametrize(
    "description",
    [
        "Health check not completed",
        "Health check never completed",
        "Проверка не завершена",
        "Проверка завершена неуспешно",
        "Health check completed but PostgreSQL is unavailable",
        "Проверка завершена. PostgreSQL недоступен",
        "Health check completed. Disk full",
        "Health check completed. High latency",
        "Информационное сообщение",
        "Резервное копирование успешно завершено",
        "Проверка завершена. Не удалось восстановить PostgreSQL",
        "Health check completed with warnings",
        "Проверка завершена с проблемами",
        "Health check completed?",
        "Возможно, проверка завершена",
        "Health check completed. CPU utilization 99%",
    ],
)
def test_info_p4_and_mixed_or_negative_messages_still_search(db, description):
    item = db.get(Incident, "event")
    item.title, item.description = "Состояние приложения", description
    item.severity, item.priority, item.needs_review = "info", "P4", False
    db.commit()
    calls = []
    refresh_recommendations(db, "event", lambda *args: calls.append(1) or [{"title": "Check"}])
    assert calls == [1]
    assert db.get(Incident, "event").recommendation_status == "ready"


@pytest.mark.parametrize(
    "field,value",
    [
        ("severity", "critical"),
        ("priority", "P2"),
        ("needs_review", True),
    ],
)
def test_ambiguous_classification_prevents_no_intervention_claim(db, field, value):
    item = db.get(Incident, "event")
    item.title, item.description = "Health check completed successfully", ""
    item.severity, item.priority, item.needs_review = "info", "P4", False
    setattr(item, field, value)
    db.commit()
    calls = []
    refresh_recommendations(db, "event", lambda *args: calls.append(1) or [])
    assert calls == [1]

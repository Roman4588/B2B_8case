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

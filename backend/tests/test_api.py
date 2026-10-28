import pytest
from app.auth import hash_password
from app.db import get_db
from app.main import app
from app.models import Base, ImportJob, Incident, Operator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.accounts import attempts
    attempts.clear()
    from app.config import settings

    monkeypatch.setattr(settings(), "upload_dir", tmp_path)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Operator(name="Инженер", email="engineer@example.org", password_hash=hash_password("test-password")))
        db.add(
            Incident(
                id="test-event",
                source="test",
                external_id="1",
                title="Disk full",
                severity="critical",
                category="server",
                priority="P1",
            )
        )
        db.commit()

    def override():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()


def login(client):
    assert client.post("/api/auth/login", json={"email": "engineer@example.org", "password": "test-password"}).status_code == 200


def test_requires_auth_and_records_manual_action(client):
    http, _ = client
    assert http.get("/api/incidents").status_code == 401
    assert http.post("/api/auth/login", json={"email": "engineer@example.org", "password": "wrong"}).status_code == 401
    login(http)
    assert http.get("/api/incidents").json()["total"] == 1
    response = http.post("/api/incidents/test-event/actions", json={"action": "accept", "comment": "Проверю"})
    assert response.status_code == 200
    assert response.json()["handling"] == "accepted"
    assert len(http.get("/api/audit").json()) == 1
    http.post("/api/incidents/test-event/actions", json={"action": "accept"})
    assert len(http.get("/api/audit").json()) == 1
    http.post("/api/auth/logout")
    assert http.get("/api/auth/me").status_code == 401


def test_upload_is_persisted_and_queued_without_processing(client):
    http, engine = client
    login(http)
    response = http.post(
        "/api/runbooks/import",
        files={"file": ("../../runbook.txt", "Если заполнен диск → Проверить место".encode())},
    )
    assert response.status_code == 202
    body = response.json()
    with Session(engine) as db:
        job = db.get(ImportJob, body["id"])
        assert job.status == "queued"
        assert ".." not in job.path
        assert db.scalar(select(ImportJob)) is not None


def test_rejects_invalid_runbook_and_cross_origin_write(client):
    http, _ = client
    login(http)
    assert http.post("/api/runbooks", json={"title": "x", "condition": "", "steps": []}).status_code == 422
    assert (
        http.post(
            "/api/incidents/test-event/actions",
            json={"action": "accept"},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )


def test_source_status_expires_when_background_polling_stops(client):
    from datetime import timedelta

    from app.models import SourceState, utcnow

    http, engine = client
    login(http)
    with Session(engine) as db:
        state = SourceState(id="prometheus", last_success=utcnow())
        db.add(state)
        db.commit()
    assert http.get("/api/sources").json()["status"] == "online"
    with Session(engine) as db:
        db.get(SourceState, "prometheus").last_success = utcnow() - timedelta(minutes=2)
        db.commit()
    assert http.get("/api/sources").json()["status"] == "stale"
    with Session(engine) as db:
        db.get(SourceState, "prometheus").error = "Unavailable"
        db.commit()
    assert http.get("/api/sources").json()["status"] == "error"


def test_handling_filter_and_recommendation_retry(client):
    http, _ = client
    login(http)
    assert http.get("/api/incidents?handling=new&priority=P1").json()["total"] == 1
    assert http.get("/api/incidents?handling=accepted").json()["total"] == 0
    assert http.get("/api/incidents?handling=invalid").status_code == 422
    assert http.post("/api/incidents/test-event/recommendations/retry").status_code == 202
    assert http.post("/api/incidents/missing/recommendations/retry").status_code == 404


def test_incident_history_is_authenticated_and_isolated(client):
    from app.models import AuditEntry

    http, engine = client
    assert http.get("/api/incidents/test-event/history").status_code == 401
    login(http)
    with Session(engine) as db:
        db.add(Incident(id="other", source="test", external_id="2", title="Another episode"))
        db.add(AuditEntry(actor="Other", action="accept", incident_id="other", comment="Other episode"))
        db.commit()
    http.post("/api/incidents/test-event/actions", json={"action": "accept", "comment": "Checked host"})
    http.post("/api/incidents/test-event/actions", json={"action": "complete", "comment": "Done manually"})
    rows = http.get("/api/incidents/test-event/history").json()
    assert [row["action"] for row in rows] == ["accept", "complete"]
    assert [row["comment"] for row in rows] == ["Checked host", "Done manually"]
    assert all(row["incident_id"] == "test-event" for row in rows)
    assert http.get("/api/incidents/missing/history").status_code == 404

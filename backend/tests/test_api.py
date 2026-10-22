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
    from app.config import settings
    monkeypatch.setattr(settings(), "upload_dir", tmp_path)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Operator(name="Инженер", password_hash=hash_password("test-password")))
        db.add(Incident(id="test-event", source="test", external_id="1", title="Disk full",
                        severity="critical", category="server", priority="P1"))
        db.commit()
    def override():
        with Session(engine, expire_on_commit=False) as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()


def login(client):
    assert client.post("/api/auth/login", json={"password": "test-password"}).status_code == 200


def test_requires_auth_and_records_manual_action(client):
    http, _ = client
    assert http.get("/api/incidents").status_code == 401
    assert http.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
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
    response = http.post("/api/runbooks/import", files={"file": ("../../runbook.txt", "Если заполнен диск → Проверить место".encode())})
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
    assert http.post("/api/incidents/test-event/actions", json={"action": "accept"},
                     headers={"Origin": "https://attacker.example"}).status_code == 403

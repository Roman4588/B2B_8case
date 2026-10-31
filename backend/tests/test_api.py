import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.db import get_db
from app.main import app
from app.models import Base, ImportJob, Incident, Operator


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.accounts import attempts

    attempts.clear()
    from app.config import settings

    monkeypatch.setattr(settings(), "upload_dir", tmp_path)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            Operator(
                name="Инженер", email="engineer@example.org", password_hash=hash_password("test-password")
            )
        )
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
    assert (
        client.post(
            "/api/auth/login", json={"email": "engineer@example.org", "password": "test-password"}
        ).status_code
        == 200
    )


def test_demo_failure_does_not_fabricate_monitoring(client, monkeypatch):
    import httpx

    from app.config import settings
    from app.models import SourceState

    test_client, engine = client
    login(test_client)
    monkeypatch.setattr(settings(), "demo_mode", True)

    def offline(*args, **kwargs):
        raise httpx.ConnectError("exporter offline")

    monkeypatch.setattr(httpx, "post", offline)
    assert test_client.post("/api/demo", json={"scenario": "outage"}).status_code == 503
    with Session(engine) as db:
        assert db.get(SourceState, "prometheus") is None


def test_compact_search_runs_in_worker_without_loading_local_model(client, monkeypatch):
    from types import SimpleNamespace

    import app.knowledge as knowledge
    import app.main as api
    import app.tasks as tasks

    http, _ = client
    login(http)
    monkeypatch.setattr(api, "settings", lambda: SimpleNamespace(search_in_worker=True))

    def forbidden(*args, **kwargs):
        raise AssertionError("API must not load a second embedding model")

    monkeypatch.setattr(knowledge, "search_runbooks", forbidden)
    expected = [{"id": "worker-hit", "title": "Очередь заказов", "similarity": 0.8}]
    monkeypatch.setattr(
        tasks.semantic_search,
        "delay",
        lambda query, limit: SimpleNamespace(get=lambda **kwargs: expected, forget=lambda: None),
    )
    response = http.get("/api/runbooks", params={"q": "Заказы стоят"})
    assert response.status_code == 200
    assert response.json() == {"items": expected, "semantic": True}


def test_compact_search_worker_timeout_is_explicit_error(client, monkeypatch):
    from types import SimpleNamespace

    import app.main as api
    import app.tasks as tasks

    http, _ = client
    login(http)
    monkeypatch.setattr(api, "settings", lambda: SimpleNamespace(search_in_worker=True))

    def timeout(**kwargs):
        raise TimeoutError("worker busy")

    monkeypatch.setattr(
        tasks.semantic_search, "delay", lambda query, limit: SimpleNamespace(get=timeout, forget=lambda: None)
    )
    response = http.get("/api/runbooks", params={"q": "Очередь"})
    assert response.status_code == 503
    assert "Модель поиска недоступна" in response.json()["detail"]


def test_requires_auth_and_records_manual_action(client):
    http, _ = client
    assert http.get("/api/incidents").status_code == 401
    assert (
        http.post("/api/auth/login", json={"email": "engineer@example.org", "password": "wrong"}).status_code
        == 401
    )
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


def make_admin(engine):
    with Session(engine) as db:
        user = db.scalar(select(Operator).where(Operator.email == "engineer@example.org"))
        user.role = "admin"
        db.commit()


def test_delete_instruction_requires_admin_and_removes_search_chunks(client):
    from app.models import AuditEntry, Chunk, Runbook

    http, engine = client
    login(http)
    with Session(engine) as db:
        book = Runbook(title="Wrong guide", condition="Wrong document", steps=["Check"])
        db.add(book)
        db.commit()
        book_id = book.id
        db.add(Chunk(runbook_id=book_id, text="Wrong", embedding=[0.0] * 384))
        incident = db.get(Incident, "test-event")
        incident.recommendations = [{"id": book_id}]
        incident.recommendation_status = "ready"
        db.commit()
    assert http.delete("/api/runbooks/" + book_id).status_code == 403
    make_admin(engine)
    assert http.delete("/api/runbooks/" + book_id).status_code == 200
    with Session(engine) as db:
        assert db.get(Runbook, book_id) is None
        assert not db.scalars(select(Chunk).where(Chunk.runbook_id == book_id)).all()
        assert db.get(Incident, "test-event").recommendations == []
        assert db.scalar(select(AuditEntry).where(AuditEntry.action == "runbook_delete"))
    assert http.delete("/api/runbooks/" + book_id).status_code == 404


def test_delete_import_only_removes_its_own_instructions_and_file(client):
    from app.config import settings
    from app.models import Runbook

    http, engine = client
    login(http)
    make_admin(engine)
    path = settings().upload_dir / "wrong.md"
    path.write_text("wrong")
    with Session(engine) as db:
        job = ImportJob(filename="same.md", path=str(path), status="succeeded")
        other = ImportJob(
            filename="same.md", path=str(settings().upload_dir / "other.md"), status="succeeded"
        )
        db.add_all([job, other])
        db.commit()
        job_id = job.id
        db.add_all(
            [
                Runbook(title="Delete", condition="Imported", steps=["x"], content_key=f"{job.id}:0"),
                Runbook(title="Keep", condition="Imported", steps=["x"], content_key=f"{other.id}:0"),
            ]
        )
        db.commit()
    response = http.delete("/api/jobs/" + job_id)
    assert response.status_code == 200
    assert response.json()["deleted_instructions"] == 1
    assert not path.exists()
    with Session(engine) as db:
        assert [b.title for b in db.scalars(select(Runbook)).all()] == ["Keep"]
        assert db.get(ImportJob, job_id).status == "deleted"
    assert all(j["id"] != job_id for j in http.get("/api/jobs").json())
    assert http.post("/api/jobs/" + job_id + "/retry").status_code == 409


def test_running_import_cannot_be_deleted(client):
    http, engine = client
    login(http)
    make_admin(engine)
    with Session(engine) as db:
        job = ImportJob(filename="busy.md", path="/data/busy.md", status="running")
        db.add(job)
        db.commit()
        job_id = job.id
    assert http.delete("/api/jobs/" + job_id).status_code == 409


def test_cancelled_queued_import_is_not_resurrected(client):
    from app.config import settings
    from app.tasks import _process_import

    http, engine = client
    login(http)
    make_admin(engine)
    path = settings().upload_dir / "cancel.json"
    path.write_text("[]")
    with Session(engine) as db:
        job = ImportJob(filename="cancel.json", path=str(path), status="queued")
        db.add(job)
        db.commit()
        job_id = job.id
    assert http.delete("/api/jobs/" + job_id).status_code == 200
    with Session(engine) as db:
        _process_import(db, job_id)
        assert db.get(ImportJob, job_id).status == "deleted"


def test_delete_import_rejects_path_outside_uploads(client, tmp_path):
    http, engine = client
    login(http)
    make_admin(engine)
    outside = tmp_path.parent / (tmp_path.name + "-outside.txt")
    outside.write_text("Keep this file")
    try:
        with Session(engine) as db:
            job = ImportJob(filename="outside.txt", path=str(outside), status="failed")
            db.add(job)
            db.commit()
            job_id = job.id
        assert http.delete("/api/jobs/" + job_id).status_code == 409
        assert outside.read_text() == "Keep this file"
    finally:
        outside.unlink()

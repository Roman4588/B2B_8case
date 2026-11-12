# ruff: noqa: F811
import json
from datetime import timedelta

import pytest
from app.models import AuditEntry, Incident, Runbook, utcnow
from app.monitoring import ingest_alerts
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from test_api import client, login  # noqa: F401

CORRECTION = {"severity": "info", "category": "network", "priority": "P2", "comment": "Проверено"}
PATH = "/api/incidents/test-event/classification"


def test_correction_auth_validation_idempotence_and_effective_queries(client):
    http, engine = client
    assert http.put(PATH, json=CORRECTION).status_code == 401
    login(http)
    assert http.put(PATH, json={**CORRECTION, "priority": "P0"}).status_code == 422
    assert http.put(PATH, json=CORRECTION, headers={"Origin": "https://evil.test"}).status_code == 403
    result = http.put(PATH, json=CORRECTION)
    assert result.status_code == 200
    body = result.json()
    assert (body["severity"], body["category"], body["priority"]) == ("info", "network", "P2")
    assert body["automatic_classification"]["severity"] == "critical"
    assert body["confidence"] is None
    assert body["classification_correction"]["actor"] == "Инженер"
    assert body["classification_correction"]["operator_id"]
    assert body["classification_correction"]["updated_at"]
    assert (
        http.put(PATH, json=CORRECTION).json()["classification_correction"]
        == body["classification_correction"]
    )
    assert len(http.get("/api/audit").json()) == 1
    assert http.get("/api/incidents?severity=critical").json()["total"] == 0
    assert http.get("/api/incidents?severity=info&category=network&priority=P2").json()["total"] == 1
    assert http.get("/api/summary").json()["info"] == 1
    assert http.get("/api/summary").json()["critical"] == 0
    assert http.put(PATH, json={**CORRECTION, "priority": "P4"}).status_code == 200
    audit = http.get("/api/audit").json()
    assert len(audit) == 2
    assert audit[0]["details"]["before"]["priority"] == "P2"
    assert audit[0]["details"]["after"]["priority"] == "P4"
    from app.models import ClassificationCorrection

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ClassificationCorrection)) == 1
        assert db.get(Incident, "test-event").priority == "P1"


def test_correction_audit_failure_rolls_back(client):
    http, engine = client
    login(http)

    def fail_audit(mapper, connection, target):
        raise RuntimeError("audit unavailable")

    event.listen(AuditEntry, "before_insert", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            http.put(PATH, json=CORRECTION)
    finally:
        event.remove(AuditEntry, "before_insert", fail_audit)
    assert http.get("/api/incidents/test-event").json()["classification_correction"] is None


def test_ingest_preserves_correction_but_new_episode_does_not_inherit(client):
    http, engine = client
    login(http)
    started = utcnow() - timedelta(minutes=5)
    alert = {
        "state": "firing",
        "activeAt": started.isoformat(),
        "labels": {"alertname": "DiskFull"},
        "annotations": {"summary": "Disk full"},
    }
    with Session(engine) as db:
        incident_id = ingest_alerts(db, [alert], "prometheus")[0]
    path = f"/api/incidents/{incident_id}/classification"
    assert http.put(path, json=CORRECTION).status_code == 200
    alert["annotations"]["summary"] = "Disk critical"
    with Session(engine) as db:
        ingest_alerts(db, [alert], "prometheus")
    assert http.get(f"/api/incidents/{incident_id}").json()["priority"] == "P2"
    alert["activeAt"] = (started + timedelta(minutes=1)).isoformat()
    with Session(engine) as db:
        new_id = ingest_alerts(db, [alert], "prometheus")[0]
    assert new_id != incident_id
    assert http.get(f"/api/incidents/{new_id}").json()["classification_correction"] is None


def seed_recommendation(engine):
    with Session(engine) as db:
        book = Runbook(
            id="book", title="Disk full", condition="Disk full", steps=["Check disk"], status="ready"
        )
        db.add(book)
        row = db.get(Incident, "test-event")
        row.recommendations = [
            {
                "id": "book",
                "revision": 1,
                "title": book.title,
                "condition": book.condition,
                "steps": book.steps,
                "similarity": 0.8,
            }
        ]
        row.recommendation_generation = 5
        row.recommendation_status = "ready"
        db.commit()


def test_feedback_unique_revision_generation_aggregates_and_audit(client):
    http, engine = client
    seed_recommendation(engine)
    path = "/api/incidents/test-event/recommendations/book/feedback"
    data = {"helpful": True, "revision": 1, "generation": 5}
    assert http.put(path, json=data).status_code == 401
    login(http)
    assert http.put(path, json={**data, "revision": 2}).status_code == 409
    assert http.put(path, json={**data, "generation": 4}).status_code == 409
    assert http.put(path, json={**data, "helpful": "yes"}).status_code == 422
    first = http.put(path, json=data)
    assert first.status_code == 200
    assert first.json()["helpful"] is True
    assert first.json()["operator_id"] and first.json()["updated_at"]
    assert http.put(path, json=data).json() == first.json()
    assert len(http.get("/api/audit").json()) == 1
    rec = http.get("/api/incidents/test-event").json()["recommendations"][0]
    assert rec["feedback"]["helpful"] is True
    assert http.put(path, json={**data, "helpful": False}).status_code == 200
    book = http.get("/api/runbooks").json()["items"][0]
    assert book["helpful_count"] == 0 and book["not_helpful_count"] == 1
    with Session(engine) as db:
        from app.models import RecommendationFeedback

        feedback = db.scalar(select(RecommendationFeedback))
        assert feedback.recommendation_snapshot["condition"] == "Disk full"
        db.get(Runbook, "book").revision = 2
        db.get(Incident, "test-event").recommendations = []
        db.get(Incident, "test-event").recommendation_generation += 1
        db.commit()
    assert http.put(path, json=data).status_code == 409
    assert http.get("/api/incidents/test-event").json()["handling"] == "new"
    assert len(http.get("/api/audit").json()) == 2


def test_lexical_explanation_and_empty_evaluation(tmp_path):
    from app.explanations import matched_terms

    assert matched_terms("Если ДИСК, disk: full! и the CPU", "диск DISK full cpu и the") == [
        "cpu",
        "disk",
        "full",
        "диск",
    ]
    assert matched_terms("нет места", "storage exhausted") == []
    from scripts.evaluate import evaluate

    path = tmp_path / "empty.json"
    path.write_text("[]")
    result = evaluate(path)
    assert result["samples"] == 0 and result["metrics"] == {} and result["passed"] is None


def test_export_uses_saved_inputs_and_evaluates_automatic_classifier(client, tmp_path):
    http, engine = client
    login(http)
    with Session(engine) as db:
        row = db.get(Incident, "test-event")
        row.description = "token=super-secret engineer@example.org"
        row.labels = {"severity": "critical", "category": "server", "password": "secret"}
        db.commit()
    http.put(PATH, json=CORRECTION)
    with Session(engine) as db:
        db.get(Incident, "test-event").title = "Later title"
        db.commit()
    from scripts.export_corrections import export_examples

    with Session(engine) as db:
        examples = export_examples(db)
    assert examples[0]["title"] == "Disk full"
    assert examples[0]["labels"] == {"severity": "critical", "category": "server"}
    assert "super-secret" not in json.dumps(examples) and "engineer@example.org" not in json.dumps(examples)
    path = tmp_path / "examples.json"
    path.write_text(json.dumps(examples), encoding="utf-8")
    from scripts.evaluate import evaluate

    assert evaluate(path)["metrics"]["severity"] == 0


def test_effective_priority_controls_sorting(client):
    http, engine = client
    login(http)
    with Session(engine) as db:
        db.add(Incident(id="other", source="test", external_id="other", title="Second", priority="P2"))
        db.commit()
    http.put(PATH, json={**CORRECTION, "priority": "P4"})
    assert [item["id"] for item in http.get("/api/incidents").json()["items"]] == ["other", "test-event"]


def test_feedback_audit_failure_rolls_back(client):
    http, engine = client
    login(http)
    seed_recommendation(engine)

    def fail_audit(mapper, connection, target):
        raise RuntimeError("audit unavailable")

    event.listen(AuditEntry, "before_insert", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            http.put(
                "/api/incidents/test-event/recommendations/book/feedback",
                json={"helpful": True, "revision": 1, "generation": 5},
            )
    finally:
        event.remove(AuditEntry, "before_insert", fail_audit)
    assert http.get("/api/incidents/test-event").json()["recommendations"][0]["feedback"] is None
    book = http.get("/api/runbooks").json()["items"][0]
    assert (book["helpful_count"], book["not_helpful_count"]) == (0, 0)


def test_feedback_is_per_author_and_revision_but_summary_combines_revisions(client):
    from app.auth import hash_password
    from app.models import Operator, RecommendationFeedback

    http, engine = client
    login(http)
    seed_recommendation(engine)
    path = "/api/incidents/test-event/recommendations/book/feedback"
    assert http.put(path, json={"helpful": True, "revision": 1, "generation": 5}).status_code == 200
    with Session(engine) as db:
        db.add(
            Operator(name="Second", email="second@example.org", password_hash=hash_password("test-password"))
        )
        incident = db.get(Incident, "test-event")
        incident.recommendation_generation = 6
        incident.recommendations = [
            {**incident.recommendations[0], "revision": 2, "condition": "New condition"}
        ]
        db.get(Runbook, "book").revision = 2
        db.commit()
    assert http.put(path, json={"helpful": False, "revision": 2, "generation": 6}).status_code == 200
    assert (
        http.post(
            "/api/auth/login", json={"email": "second@example.org", "password": "test-password"}
        ).status_code
        == 200
    )
    assert http.get("/api/incidents/test-event").json()["recommendations"][0]["feedback"] is None
    assert http.put(path, json={"helpful": True, "revision": 2, "generation": 6}).status_code == 200
    book = http.get("/api/runbooks").json()["items"][0]
    assert (book["helpful_count"], book["not_helpful_count"], book["usefulness_scope"]) == (
        2,
        1,
        "all_revisions",
    )
    with Session(engine) as db:
        old = db.scalar(select(RecommendationFeedback).where(RecommendationFeedback.revision == 1))
        assert old.recommendation_snapshot["condition"] == "Disk full"


def test_existing_recommendation_gets_factual_explanation(client):
    http, engine = client
    login(http)
    seed_recommendation(engine)
    recommendation = http.get("/api/incidents/test-event").json()["recommendations"][0]
    assert recommendation["matched_terms"] == ["disk", "full"]
    assert "не вероятность" in recommendation["explanation"]


@pytest.mark.parametrize(
    "text",
    [
        "client_secret=topsecret",
        "access_token=topsecret",
        'password="first second"',
        "refresh_token='first second'",
        '"api_key": "first second"',
    ],
)
def test_export_redacts_compound_keys_and_entire_quoted_secrets(text):
    from scripts.export_corrections import redact

    result = redact(text)
    assert "topsecret" not in result and "first" not in result and "second" not in result


@pytest.mark.parametrize("kind", ["book", "import"])
def test_deleting_instruction_preserves_feedback_snapshot(client, kind):
    from pathlib import Path

    from app.config import settings
    from app.models import ImportJob, RecommendationFeedback
    from test_api import make_admin

    http, engine = client
    login(http)
    make_admin(engine)
    seed_recommendation(engine)
    assert (
        http.put(
            "/api/incidents/test-event/recommendations/book/feedback",
            json={"helpful": True, "revision": 1, "generation": 5},
        ).status_code
        == 200
    )
    with Session(engine) as db:
        if kind == "import":
            path = Path(settings().upload_dir) / "feedback-delete.txt"
            path.write_text("Test instruction", encoding="utf-8")
            job = ImportJob(id="job-feedback", filename=path.name, path=str(path), status="done")
            db.add(job)
            db.get(Runbook, "book").content_key = "job-feedback:0"
            db.commit()
        # SQLite must enforce the same foreign-key behavior as PostgreSQL here.
        db.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))
    response = http.delete("/api/runbooks/book" if kind == "book" else "/api/jobs/job-feedback")
    assert response.status_code == 200
    with Session(engine) as db:
        assert db.get(Runbook, "book") is None
        feedback = db.scalar(select(RecommendationFeedback))
        assert feedback.runbook_id == "book"
        assert feedback.recommendation_snapshot["condition"] == "Disk full"
        assert feedback.helpful is True
    assert http.get("/api/runbooks").json()["items"] == []


def test_worker_search_includes_persisted_usefulness_counts(client, monkeypatch):
    from types import SimpleNamespace

    from app import tasks
    from app.config import settings

    http, engine = client
    login(http)
    seed_recommendation(engine)
    assert (
        http.put(
            "/api/incidents/test-event/recommendations/book/feedback",
            json={"helpful": True, "revision": 1, "generation": 5},
        ).status_code
        == 200
    )
    # Only the external Celery search is substituted; aggregates use the real database.
    result = SimpleNamespace(get=lambda **kwargs: [{"id": "book", "title": "Disk full"}], forget=lambda: None)
    monkeypatch.setattr(settings(), "search_in_worker", True)
    monkeypatch.setattr(tasks.semantic_search, "delay", lambda *args: result)
    response = http.get("/api/runbooks?q=disk")
    assert response.status_code == 200
    assert response.json()["items"][0]["helpful_count"] == 1
    assert response.json()["items"][0]["not_helpful_count"] == 0

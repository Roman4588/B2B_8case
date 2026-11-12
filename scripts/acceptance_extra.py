"""Synthetic live checks. Run only on the disposable acceptance Compose stack.

Uses HTTP, the real worker and its shared uploads volume. For retry, the test
repairs only its own deliberately malformed uploaded file after failure.
"""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx
from app.db import session_factory
from app.models import ImportJob


def wait(read, expected, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = read()
        if value == expected:
            return
        time.sleep(1)
    raise AssertionError(f"Expected {expected!r}, got {value!r}")


def main():
    base = os.getenv("BASE_URL", "http://frontend")
    token = uuid4().hex[:12]
    report = {}
    with (
        httpx.Client(base_url=base, timeout=30) as admin,
        httpx.Client(base_url=base, timeout=30) as engineer,
    ):
        admin.post(
            "/api/auth/login", json={"email": os.environ["E2E_EMAIL"], "password": os.environ["E2E_PASSWORD"]}
        ).raise_for_status()
        email = f"qa-{token}@example.org"
        password, changed = "Synthetic-initial-2026", "Synthetic-changed-2026"
        response = admin.post(
            "/api/users",
            json={"email": email, "name": f"QA {token}", "password": password, "role": "engineer"},
        )
        assert response.status_code == 201, response.text
        user_id = response.json()["id"]
        engineer.post("/api/auth/login", json={"email": email, "password": password}).raise_for_status()
        assert engineer.get("/api/auth/me").json()["must_change_password"]
        engineer.post(
            "/api/auth/password", json={"current_password": password, "new_password": changed}
        ).raise_for_status()
        assert not engineer.get("/api/auth/me").json()["must_change_password"]
        assert engineer.get("/api/users").status_code == 403
        report["engineer_login_password_change_admin_boundary"] = True
        body = {
            "title": f"QA network {token}",
            "condition": "Network packet loss on gateway, gateway unreachable",
            "steps": ["Inspect interface counters"],
            "category": "network",
        }
        response = engineer.post("/api/runbooks", json=body)
        assert response.status_code == 202, response.text
        book_id = response.json()["id"]

        def book():
            return next(b for b in admin.get("/api/runbooks").json()["items"] if b["id"] == book_id)

        wait(lambda: book()["status"], "ready")
        response = engineer.patch(
            f"/api/runbooks/{book_id}",
            json={**body, "steps": ["Inspect interface counters", "Escalate to network engineer"]},
        )
        assert response.status_code == 202 and response.json()["revision"] == 2
        wait(lambda: book()["status"], "ready")
        found = engineer.get("/api/runbooks", params={"q": body["condition"]})
        found.raise_for_status()
        assert any(b["id"] == book_id for b in found.json()["items"])
        assert engineer.delete(f"/api/runbooks/{book_id}").status_code == 403
        admin.delete(f"/api/runbooks/{book_id}").raise_for_status()
        report["engineer_create_edit_real_search_admin_delete"] = True
        response = engineer.post(
            "/api/runbooks/import", files={"file": (f"qa-retry-{token}.json", b"{broken", "application/json")}
        )
        assert response.status_code == 202
        job_id = response.json()["id"]

        def read_status():
            return admin.get(f"/api/jobs/{job_id}").json()["status"]

        wait(read_status, "failed")
        with session_factory()() as db:
            job = db.get(ImportJob, job_id)
            Path(job.path).write_text(json.dumps([body]), encoding="utf-8")
        response = engineer.post(f"/api/jobs/{job_id}/retry")
        assert response.status_code == 202, response.text
        wait(read_status, "succeeded")
        assert engineer.delete(f"/api/jobs/{job_id}").status_code == 403
        admin.delete(f"/api/jobs/{job_id}").raise_for_status()
        report["real_queue_failure_repaired_fixture_retry_and_delete"] = True
        engineer.post("/api/auth/logout").raise_for_status()
        assert engineer.get("/api/auth/me").status_code == 401
        admin.patch(f"/api/users/{user_id}", json={"is_active": False}).raise_for_status()
        report["logout_and_deactivate_synthetic_account"] = True
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

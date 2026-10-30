"""Additional HTTP acceptance for the Amvera packaging; demonstration DB only.

Provision a separate engineer, exercise the existing full smoke and imports.
Secrets are supplied by environment and never written to the report.
"""
import argparse
import json
import os
import secrets
from pathlib import Path

import httpx
from smoke import main as smoke_main
from smoke import wait_for


def verify(base_url):
    wait_for(lambda: httpx.get(base_url + "/api/health/ready", timeout=10).json(),
             lambda value: value.get("status") == "ready", 600)
    engineer_email = "reviewer-" + secrets.token_hex(4) + "@example.org"
    engineer_password = "Signalis" + secrets.token_urlsafe(24) + "7"
    temporary_password = "Initial" + secrets.token_urlsafe(24) + "9"
    with httpx.Client(base_url=base_url, timeout=30) as admin:
        admin.post("/api/auth/login", json={"email": os.environ["E2E_EMAIL"],
                                          "password": os.environ["E2E_PASSWORD"]}).raise_for_status()
        admin.post("/api/users", json={"email": engineer_email, "password": temporary_password,
                                      "name": "Amvera preflight reviewer", "role": "engineer"}).raise_for_status()
    with httpx.Client(base_url=base_url, timeout=30) as client:
        client.post("/api/auth/login", json={"email": engineer_email, "password": temporary_password}).raise_for_status()
        client.post("/api/auth/password", json={"current_password": temporary_password,
                                               "new_password": engineer_password}).raise_for_status()
    # Existing acceptance now runs with the engineer rather than the administrator.
    os.environ["E2E_EMAIL"], os.environ["E2E_PASSWORD"] = engineer_email, engineer_password
    report = smoke_main(base_url)
    with httpx.Client(base_url=base_url, timeout=30) as client:
        client.post("/api/auth/login", json={"email": engineer_email, "password": engineer_password}).raise_for_status()
        assert client.get("/api/auth/me").json()["role"] == "engineer"
        assert client.get("/api/users").status_code == 403
        report["checks"]["engineer_has_no_admin_access"] = True
        assert client.get("/").status_code == 200
        assert client.get("/api/auth/me").status_code == 200
        report["checks"]["session_after_page_request"] = True
        source = wait_for(lambda: client.get("/api/sources").json(), lambda value: value.get("status") == "online")
        first_success = source["state"]["last_success"]
        wait_for(lambda: client.get("/api/sources").json(),
                 lambda value: value["state"]["last_success"] != first_success, 60)
        report["checks"]["prometheus_poll_timestamp_advances"] = True
        # Both states must arrive through exporter -> actual Prometheus -> worker -> DB.
        for scenario, minimum, maximum in (("normal", 1, 1), ("outage", 5, 5)):
            client.post("/api/demo", json={"scenario": scenario}).raise_for_status()
            wait_for(lambda: client.get("/api/incidents", params={"state": "firing"}).json(),
                     lambda value: minimum <= value.get("total", 0) <= maximum, 120)
        report["checks"]["scenario_changes_prometheus_events"] = True
        event = client.get("/api/incidents", params={"state": "firing"}).json()["items"][0]
        if event["handling"] == "new":
            client.post(f"/api/incidents/{event['id']}/actions", json={"action": "accept"}).raise_for_status()
        completed = client.post(f"/api/incidents/{event['id']}/actions", json={"action": "complete"})
        completed.raise_for_status()
        assert completed.json()["handling"] == "completed"
        count = len(client.get("/api/audit").json())
        client.post(f"/api/incidents/{event['id']}/actions", json={"action": "complete"}).raise_for_status()
        assert len(client.get("/api/audit").json()) == count
        assert any(row["action"] == "complete" and row["incident_id"] == event["id"]
                   for row in client.get("/api/audit").json())
        report["checks"]["manual_completion_audit_and_idempotence"] = True
        root = Path(__file__).resolve().parents[1]
        upload = client.post("/api/runbooks/import", files={"file": ("reviewer-queue.json",
                              (root / "examples/reviewer-queue.json").read_bytes(), "application/json")})
        assert upload.status_code == 202
        job = wait_for(lambda: client.get("/api/jobs/" + upload.json()["id"]).json(),
                       lambda value: value["status"] in {"succeeded", "failed"}, 300)
        assert job["status"] == "succeeded", job
        results = client.get("/api/runbooks", params={"q": "Заказы стоят, обработчик не забирает сообщения"})
        results.raise_for_status()
        assert any(row["title"] == "Очередь заказов Маяк не обрабатывается" for row in results.json()["items"])
        report["checks"]["json_worker_import_and_paraphrased_search"] = True
        markdown = "# Регламент контрольной очереди\n\n## Симптомы\nОчередь сообщений не обрабатывается.\n\n## Действия\nПроверить обработчик и брокер.\n\n## Ограничения\nНе удалять сообщения."
        upload = client.post("/api/runbooks/import", files={"file": ("narrative.md", markdown.encode(), "text/markdown")})
        assert upload.status_code == 202
        job = wait_for(lambda: client.get("/api/jobs/" + upload.json()["id"]).json(),
                       lambda value: value["status"] in {"succeeded", "failed"}, 300)
        assert job["status"] == "succeeded" and job["total"] == 1, job
        report["checks"]["narrative_markdown_one_runbook"] = True
        report["indexed_runbooks"] = client.get("/api/health/ready").json()["indexed_runbooks"]
        # Report only identities, never passwords or cookies.
        report["demonstration_engineer_email"] = engineer_email
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = verify(args.url)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

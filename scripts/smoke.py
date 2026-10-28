"""End-to-end acceptance over HTTP against the running Compose stack."""

import argparse
import json
import os
import time
from io import BytesIO
from pathlib import Path

import httpx
from reportlab.pdfgen import canvas


def wait_for(getter, predicate, timeout=240):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = getter()
            if predicate(last):
                return last
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError(f"Timed out; last result: {last}")


def main(base_url):
    report = {"base_url": base_url, "checks": {}}
    with httpx.Client(base_url=base_url, timeout=20) as client:
        wait_for(lambda: client.get("/api/health/ready").json(), lambda v: v.get("status") == "ready", 600)
        response = client.post(
            "/api/auth/login", json={"email": os.environ["E2E_EMAIL"], "password": os.environ["E2E_PASSWORD"]}
        )
        response.raise_for_status()
        report["checks"]["login"] = True
        events = wait_for(lambda: client.get("/api/incidents").json(), lambda v: v.get("total", 0) >= 1)
        event = next(
            (e for e in events["items"] if e["severity"] != "info" and e["handling"] == "new"),
            events["items"][0],
        )
        detail = wait_for(
            lambda: client.get("/api/incidents/" + event["id"]).json(),
            lambda v: v["recommendation_status"] == "ready" and len(v["recommendations"]) > 0,
        )
        assert all(detail[k] for k in ("severity", "category", "priority"))
        report["checks"]["real_alert_and_recommendations"] = True
        if detail["handling"] == "new":
            action = client.post(
                f"/api/incidents/{event['id']}/actions",
                json={"action": "accept", "comment": "HTTP smoke: только ручное выполнение"},
            )
            action.raise_for_status()
            assert action.json()["handling"] == "accepted"
            first_count = len(client.get("/api/audit").json())
            client.post(f"/api/incidents/{event['id']}/actions", json={"action": "accept"}).raise_for_status()
            assert len(client.get("/api/audit").json()) == first_count
        report["checks"]["manual_confirmation_and_idempotence"] = True
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer)
        for page in range(60):
            pdf.drawString(
                40,
                750,
                f"If disk space is low -> Review capacity and archive approved logs. Page {page + 1}.",
            )
            pdf.showPage()
        pdf.save()
        started = time.monotonic()
        upload = client.post(
            "/api/runbooks/import",
            files={"file": ("acceptance-60-pages.pdf", buffer.getvalue(), "application/pdf")},
        )
        assert upload.status_code == 202, upload.text
        report["pdf_upload_response_seconds"] = round(time.monotonic() - started, 3)
        job_id = upload.json()["id"]
        result = wait_for(
            lambda: client.get("/api/jobs/" + job_id).json(),
            lambda v: v["status"] in {"succeeded", "failed"},
            600,
        )
        assert result["status"] == "succeeded", result
        assert result["total"] > 0
        report["checks"]["sixty_page_pdf_background_import"] = True
        report["pdf_processing_seconds"] = round(time.monotonic() - started, 3)
        report["import_job_id"] = job_id
        client.post("/api/auth/logout").raise_for_status()
        assert client.get("/api/auth/me").status_code == 401
        report["checks"]["logout"] = True
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--output", default="docs/smoke-report.json")
    args = parser.parse_args()
    result = main(args.url)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

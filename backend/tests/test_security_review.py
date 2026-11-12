# ruff: noqa: F811
"""Small synthetic regressions; no external target or exploit scanner is used."""

from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from test_api import client, login  # noqa: F401


def test_job_api_does_not_disclose_internal_storage_paths(client):
    from app.models import ImportJob

    http, engine = client
    login(http)
    with Session(engine) as db:
        db.add(
            ImportJob(
                id="private-path",
                filename="guide.txt",
                path="/srv/private/storage/guide.txt",
                status="failed",
            )
        )
        db.commit()
    for response, status in [
        (http.get("/api/jobs"), 200),
        (http.get("/api/jobs/private-path"), 200),
        (http.post("/api/jobs/private-path/retry"), 202),
    ]:
        assert response.status_code == status
        rows = response.json() if isinstance(response.json(), list) else [response.json()]
        assert all("path" not in row for row in rows)
        assert "/srv/private" not in response.text


def test_retry_rechecks_deleted_import_even_with_a_cached_row(client):
    from app.main import retry_job
    from app.models import ImportJob

    _, engine = client
    with Session(engine) as db:
        db.add(ImportJob(id="cancelled", filename="guide.txt", path="/synthetic/guide.txt", status="failed"))
        db.commit()
    with Session(engine) as stale:
        cached = stale.get(ImportJob, "cancelled")
        assert cached.status == "failed"
        with Session(engine) as admin:
            admin.get(ImportJob, "cancelled").status = "deleted"
            admin.commit()
        with pytest.raises(HTTPException) as failure:
            retry_job("cancelled", operator=SimpleNamespace(name="Engineer"), db=stale)
        assert failure.value.status_code == 409
    with Session(engine) as db:
        assert db.get(ImportJob, "cancelled").status == "deleted"


def test_pdf_extraction_stops_at_the_text_budget(monkeypatch):
    import pypdf
    from app import documents

    calls = []

    class Page:
        def get_contents(self):
            return SimpleNamespace(get_data=lambda: b"small valid-sized stream")

        def extract_text(self):
            calls.append(1)
            return "x" * 1_100_000

    monkeypatch.setattr(pypdf, "PdfReader", lambda stream: SimpleNamespace(pages=[Page() for _ in range(10)]))
    with pytest.raises(ValueError, match="слишком много текста"):
        documents.extract(b"%PDF-synthetic", ".pdf")
    assert len(calls) == 3


def test_pdf_content_is_checked_before_text_parsing(monkeypatch):
    import pypdf
    from app import documents

    calls = []

    class Page:
        def get_contents(self):
            # A small test threshold stands in for an expanded PDF stream.
            return SimpleNamespace(get_data=lambda: b"x" * 40)

        def extract_text(self):
            calls.append(1)
            return "If disk full then inspect disk"

    monkeypatch.setattr(documents, "MAX_PDF_PAGE_BYTES", 32, raising=False)
    monkeypatch.setattr(pypdf, "PdfReader", lambda stream: SimpleNamespace(pages=[Page()]))
    with pytest.raises(ValueError, match="содержимого PDF"):
        documents.extract(b"%PDF-synthetic", ".pdf")
    assert calls == []


def test_docx_text_collection_stops_at_the_budget(monkeypatch):
    from zipfile import ZipFile

    import docx
    from app import documents

    calls = []

    class Paragraph:
        @property
        def text(self):
            calls.append(1)
            return "x" * 1_100_000

    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("word/document.xml", "<document/>")
    monkeypatch.setattr(
        docx,
        "Document",
        lambda stream: SimpleNamespace(paragraphs=[Paragraph() for _ in range(10)], tables=[]),
    )
    with pytest.raises(ValueError, match="слишком много текста"):
        documents.extract(content.getvalue(), ".docx")
    assert len(calls) == 3


@pytest.mark.parametrize(
    "url",
    ["HTTPS://qa:synthetic!value@internal.example/path", "AMQPS://qa:synthetic!value@internal.example/vhost"],
)
def test_export_redacts_uri_credentials_for_uppercase_and_other_schemes(url):
    from scripts.export_corrections import redact

    result = redact(url)
    assert "synthetic" not in result and "qa:" not in result


def test_unexpected_import_error_is_not_returned_to_engineers(client, monkeypatch, tmp_path):
    from app import tasks
    from app.models import ImportJob

    http, engine = client
    login(http)
    path = tmp_path / "synthetic.txt"
    path.write_text("ordinary test data", encoding="utf-8")
    with Session(engine) as db:
        db.add(ImportJob(id="internal-error", filename=path.name, path=str(path), status="queued"))
        db.commit()

    def unexpected(*args):
        raise RuntimeError("internal /srv/private/worker-config synthetic-sensitive-detail")

    monkeypatch.setattr(tasks, "extract", unexpected)
    with Session(engine) as db:
        tasks._process_import(db, "internal-error")
    response = http.get("/api/jobs/internal-error")
    assert response.json()["status"] == "failed"
    assert "synthetic-sensitive-detail" not in response.text and "/srv/private" not in response.text

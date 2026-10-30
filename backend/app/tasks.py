import hashlib
import logging
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from celery import Celery
from sqlalchemy import select, text, update

from app.config import settings
from app.db import session_factory
from app.documents import extract, parse_runbooks
from app.knowledge import index_runbook, search_runbooks
from app.models import ImportJob, Incident, Runbook, SourceState, utcnow
from app.monitoring import fetch_alerts, ingest_alerts
from app.recommendations import has_ready_runbooks, invalidate_recommendations, refresh_recommendations

log = logging.getLogger(__name__)
celery = Celery("copilot", broker=settings().redis_url, backend=settings().redis_url)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    beat_schedule={
        "monitoring": {"task": "app.tasks.poll", "schedule": 15.0},
        "maintenance": {"task": "app.tasks.maintenance", "schedule": 8.0},
    },
)


@celery.task(name="app.tasks.semantic_search")
def semantic_search(query: str, limit: int = 20):
    with session_factory()() as db:
        return search_runbooks(db, query, limit)


def process_import(db, job_id: str):
    with import_lock(db, job_id) as acquired:
        if acquired:
            _process_import(db, job_id)


def _process_import(db, job_id: str):
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
    if job is None or job.status in {"succeeded", "running"}:
        return
    job.status, job.updated_at, job.error = "running", utcnow(), ""
    db.commit()
    try:
        path = Path(job.path)
        content = extract(path.read_bytes(), path.suffix.lower())
        records = parse_runbooks(content, path.suffix.lower(), job.filename)
        job.total = len(records)
        db.commit()
        for index, record in enumerate(records):
            key = f"{job.id}:{index}"
            book = db.scalar(select(Runbook).where(Runbook.content_key == key))
            if book is None:
                book = Runbook(**record, source=job.filename, content_key=key)
                db.add(book)
                db.commit()
            if book.status != "ready":
                index_runbook(db, book.id)
            job.progress, job.updated_at = index + 1, utcnow()
            db.commit()
        job.status = "succeeded"
        invalidate_recommendations(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(ImportJob, job_id)
        job.status, job.error, job.updated_at = "failed", str(exc)[:2000], utcnow()
        db.commit()
        log.exception("Import failed: %s", job_id)


@celery.task(name="app.tasks.import_file")
def import_file(job_id: str):
    with session_factory()() as db:
        process_import(db, job_id)


@celery.task(name="app.tasks.poll")
def poll():
    with session_factory()() as db:
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(8008)")):
            return
        try:
            alerts = fetch_alerts()
            # Validate the whole snapshot before mutating lifecycle state.
            if any(
                not isinstance(a, dict)
                or not isinstance(a.get("labels"), dict)
                or not isinstance(a.get("annotations", {}), dict)
                for a in alerts
            ):
                raise ValueError("Некорректный снимок событий Prometheus")
            ingest_alerts(db, alerts, "prometheus")
        except Exception:
            db.rollback()
            state = db.get(SourceState, "prometheus")
            if state is None:
                state = SourceState(id="prometheus")
                db.add(state)
            state.error = "Источник недоступен или вернул ошибку. Активные события сохранены."
            state.last_attempt = utcnow()
            db.commit()
            log.exception("Prometheus sync failed")


@contextmanager
def advisory_lock(db, key):
    # A dedicated connection owns a session lock, so commits during processing
    # do not let the next beat task start a second maintenance pass.
    with db.get_bind().connect() as connection:
        acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})


def maintenance_lock(db):
    return advisory_lock(db, 8009)


def import_lock(db, job_id):
    key = int.from_bytes(hashlib.sha256(f"import:{job_id}".encode()).digest()[:8], signed=True)
    return advisory_lock(db, key)


@celery.task(name="app.tasks.maintenance")
def maintenance():
    with session_factory()() as db, maintenance_lock(db) as acquired:
        if not acquired:
            return
        queued_jobs = db.scalars(select(ImportJob).where(ImportJob.status == "queued").limit(10)).all()
        for job in queued_jobs:
            import_file.delay(job.id)
        stale = utcnow() - timedelta(minutes=15)
        stale_ids = db.scalars(
            select(ImportJob.id).where(ImportJob.status == "running", ImportJob.updated_at < stale)
        ).all()
        for job_id in stale_ids:
            # Elapsed time alone cannot prove worker death. The same session lock
            # is held through extraction/indexing and released on worker disconnect.
            with import_lock(db, job_id) as available:
                if available:
                    db.execute(
                        update(ImportJob)
                        .where(
                            ImportJob.id == job_id,
                            ImportJob.status == "running",
                            ImportJob.updated_at < stale,
                        )
                        .values(status="queued", error="Повтор после прерывания обработки")
                    )
                    db.commit()
        db.commit()
        books = db.scalars(select(Runbook).where(Runbook.status == "queued").limit(30)).all()
        for book in books:
            try:
                index_runbook(db, book.id)
            except Exception:
                db.rollback()
                book = db.get(Runbook, book.id)
                book.status, book.error = (
                    "failed",
                    "Модель недоступна. Проверьте сеть и повторите индексацию.",
                )
                db.commit()
                log.exception("Indexing failed")
        events = db.scalars(
            select(Incident.id)
            .where(Incident.recommendation_status == "pending", Incident.lifecycle == "firing")
            .limit(50)
        ).all()
        if has_ready_runbooks(db):
            for incident_id in events:
                refresh_recommendations(db, incident_id, search_runbooks)

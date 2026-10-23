import hashlib
import time
from collections import defaultdict, deque
from datetime import UTC, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from app.auth import create_session, require_operator, verify_password
from app.config import settings
from app.db import get_db
from app.documents import RunbookInput
from app.models import (
    AuditEntry,
    ImportJob,
    Incident,
    LoginSession,
    Operator,
    Runbook,
    SourceState,
    uid,
    utcnow,
)
from app.operations import manual_action
from app.recommendations import invalidate_recommendations

app = FastAPI(
    title="Дежурный · ИИ-ассистент", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json"
)
attempts = defaultdict(deque)


@app.middleware("http")
async def origin_and_security(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
        if urlsplit(origin).netloc != request.headers.get("host"):
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=403, content={"detail": "Недопустимый источник запроса"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def public(row):
    return jsonable_encoder({c.name: getattr(row, c.name) for c in row.__table__.columns})


class LoginInput(BaseModel):
    password: str = Field(max_length=500)


@app.post("/api/auth/login")
def login(body: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    ip = request.client.host if request.client else "local"
    queue = attempts[ip]
    now = time.monotonic()
    while queue and queue[0] < now - 60:
        queue.popleft()
    if len(queue) >= 10:
        raise HTTPException(429, "Слишком много попыток. Повторите через минуту")
    queue.append(now)
    operator = db.scalar(select(Operator).limit(1))
    if operator is None or not verify_password(body.password, operator.password_hash):
        raise HTTPException(401, "Неверный пароль")
    queue.clear()
    token = create_session(db, operator)
    response.set_cookie(
        "copilot_session",
        token,
        httponly=True,
        samesite="strict",
        secure=settings().session_secure,
        max_age=43200,
        path="/api",
    )
    return {"id": operator.id, "name": operator.name}


@app.get("/api/auth/me")
def me(operator=Depends(require_operator)):
    return {"id": operator.id, "name": operator.name}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db=Depends(get_db)):
    token = request.cookies.get("copilot_session", "")
    record = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if record:
        db.delete(record)
        db.commit()
    response.delete_cookie("copilot_session", path="/api")
    return {"ok": True}


@app.get("/api/health/live")
def live():
    return {"status": "alive"}


@app.get("/api/health/ready")
def ready(response: Response, db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        from redis import Redis

        Redis.from_url(settings().redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
        count = db.scalar(select(func.count()).select_from(Runbook).where(Runbook.status == "ready"))
        response.status_code = 200 if count else 503
        return {"status": "ready" if count else "initializing", "indexed_runbooks": count}
    except Exception:
        response.status_code = 503
        return {"status": "unavailable", "detail": "Проверяются база данных и очередь"}


@app.get("/api/incidents")
def incidents(
    q: str = "",
    severity: str = "",
    category: str = "",
    priority: str = "",
    state: str = "",
    handling: str = "",
    page: int = 1,
    operator=Depends(require_operator),
    db=Depends(get_db),
):
    if not 1 <= page <= 100000 or len(q) > 500:
        raise HTTPException(422, "Некорректные параметры")
    if handling and handling not in {"new", "accepted", "completed", "dismissed"}:
        raise HTTPException(422, "Неизвестный статус обработки")
    stmt = select(Incident)
    for name, value in (
        ("severity", severity),
        ("category", category),
        ("priority", priority),
        ("lifecycle", state),
        ("handling", handling),
    ):
        if value:
            stmt = stmt.where(getattr(Incident, name) == value)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(
            (Incident.title.ilike(f"%{escaped}%", escape="\\"))
            | (Incident.host.ilike(f"%{escaped}%", escape="\\"))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        stmt.order_by(Incident.lifecycle, Incident.priority, Incident.last_seen.desc())
        .offset((page - 1) * 50)
        .limit(50)
    ).all()
    return {"items": [public(row) for row in rows], "total": total, "page": page}


@app.get("/api/summary")
def summary(operator=Depends(require_operator), db=Depends(get_db)):
    counts = dict(
        db.execute(
            select(Incident.severity, func.count())
            .where(Incident.lifecycle == "firing")
            .group_by(Incident.severity)
        ).all()
    )
    return {
        "critical": counts.get("critical", 0),
        "warning": counts.get("warning", 0),
        "info": counts.get("info", 0),
        "pending": db.scalar(
            select(func.count())
            .select_from(Incident)
            .where(Incident.lifecycle == "firing", Incident.handling == "new")
        ),
        "runbooks": db.scalar(select(func.count()).select_from(Runbook).where(Runbook.status == "ready")),
    }


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: str, operator=Depends(require_operator), db=Depends(get_db)):
    item = db.get(Incident, incident_id)
    if item is None:
        raise HTTPException(404, "Событие не найдено")
    return public(item)


class ActionInput(BaseModel):
    action: Literal["accept", "complete", "dismiss"]
    comment: str = Field(default="", max_length=2000)


@app.post("/api/incidents/{incident_id}/actions")
def action(incident_id: str, body: ActionInput, operator=Depends(require_operator), db=Depends(get_db)):
    try:
        return public(manual_action(db, incident_id, body.action, operator.name, body.comment))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/runbooks")
def runbooks(q: str = "", operator=Depends(require_operator), db=Depends(get_db)):
    if q.strip():
        if len(q) > 1000:
            raise HTTPException(422, "Запрос слишком длинный")
        from app.knowledge import search_runbooks

        try:
            return {"items": search_runbooks(db, q, 20), "semantic": True}
        except Exception as exc:
            raise HTTPException(503, "Модель поиска недоступна. Проверьте состояние базы знаний") from exc
    return {
        "items": [
            public(row) for row in db.scalars(select(Runbook).order_by(Runbook.created_at.desc()).limit(500))
        ],
        "semantic": False,
    }


@app.post("/api/runbooks", status_code=202)
def create_runbook(body: RunbookInput, operator=Depends(require_operator), db=Depends(get_db)):
    book = Runbook(**body.model_dump(), source=operator.name)
    db.add(book)
    db.add(AuditEntry(actor=operator.name, action="runbook_create", comment=body.title))
    db.commit()
    db.refresh(book)
    return public(book)


@app.patch("/api/runbooks/{book_id}", status_code=202)
def update_runbook(book_id: str, body: RunbookInput, operator=Depends(require_operator), db=Depends(get_db)):
    book = db.scalar(select(Runbook).where(Runbook.id == book_id).with_for_update())
    if book is None:
        raise HTTPException(404, "Инструкция не найдена")
    for key, value in body.model_dump().items():
        setattr(book, key, value)
    book.status, book.error, book.revision = "queued", "", book.revision + 1
    invalidate_recommendations(db)
    db.add(AuditEntry(actor=operator.name, action="runbook_update", comment=book.title))
    db.commit()
    return public(book)


@app.post("/api/runbooks/{book_id}/retry", status_code=202)
def retry_book(book_id: str, operator=Depends(require_operator), db=Depends(get_db)):
    book = db.get(Runbook, book_id)
    if not book:
        raise HTTPException(404, "Инструкция не найдена")
    book.status, book.error = "queued", ""
    db.commit()
    return public(book)


@app.post("/api/runbooks/import", status_code=202)
async def upload(file: UploadFile = File(...), operator=Depends(require_operator), db=Depends(get_db)):
    filename = (file.filename or "document").replace("\\", "/").split("/")[-1][:200]
    extension = Path(filename).suffix.lower()
    if extension not in {".json", ".md", ".txt", ".pdf", ".docx"}:
        raise HTTPException(415, "Поддерживаются JSON, MD, TXT, PDF и DOCX")
    content = await file.read(25 * 1024 * 1024 + 1)
    if not content or len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "Файл должен содержать от 1 байта до 25 МБ")
    folder = settings().upload_dir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (uid() + extension)
    path.write_bytes(content)
    job = ImportJob(filename=filename, path=str(path))
    db.add(job)
    db.add(AuditEntry(actor=operator.name, action="document_upload", comment=filename))
    db.commit()
    db.refresh(job)
    return public(job)


@app.get("/api/jobs")
def jobs(operator=Depends(require_operator), db=Depends(get_db)):
    return [
        public(row) for row in db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(30))
    ]


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str, operator=Depends(require_operator), db=Depends(get_db)):
    row = db.get(ImportJob, job_id)
    if row is None:
        raise HTTPException(404, "Задание не найдено")
    return public(row)


@app.post("/api/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, operator=Depends(require_operator), db=Depends(get_db)):
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")
    if job.status != "failed":
        raise HTTPException(409, "Повтор доступен для задания с ошибкой")
    job.status, job.error = "queued", ""
    db.commit()
    return public(job)


@app.get("/api/sources")
def sources(operator=Depends(require_operator), db=Depends(get_db)):
    state = db.get(SourceState, "prometheus")
    status = "waiting"
    if state:
        if state.error:
            status = "error"
        elif state.last_success:
            status = (
                "online"
                if utcnow() - state.last_success.replace(tzinfo=UTC) < timedelta(seconds=60)
                else "stale"
            )
    return {
        "source": "Prometheus",
        "state": public(state) if state else None,
        "interval_seconds": 15,
        "demo_mode": settings().demo_mode,
        "status": status,
        "stale_after_seconds": 60,
    }


@app.post("/api/incidents/{incident_id}/recommendations/retry", status_code=202)
def retry_recommendations(incident_id: str, operator=Depends(require_operator), db=Depends(get_db)):
    item = db.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
    if item is None:
        raise HTTPException(404, "Событие не найдено")
    if item.lifecycle != "firing":
        raise HTTPException(409, "Событие уже восстановлено")
    item.recommendations = []
    item.recommendation_status = "pending"
    item.recommendation_generation += 1
    db.commit()
    return {"status": "queued"}


@app.post("/api/sources/sync", status_code=202)
def sync(operator=Depends(require_operator)):
    from app.tasks import poll

    try:
        poll.delay()
    except Exception as exc:
        raise HTTPException(503, "Очередь недоступна") from exc
    return {"status": "queued"}


@app.get("/api/audit")
def audit(operator=Depends(require_operator), db=Depends(get_db)):
    return [
        public(row)
        for row in db.scalars(select(AuditEntry).order_by(AuditEntry.created_at.desc()).limit(100))
    ]


class DemoInput(BaseModel):
    scenario: Literal["normal", "outage", "warning"]


@app.post("/api/demo")
def demo(body: DemoInput, operator=Depends(require_operator), db=Depends(get_db)):
    if not settings().demo_mode:
        raise HTTPException(404, "Демонстрация отключена")
    import httpx

    try:
        httpx.post(
            settings().demo_exporter_url + "/scenario", json=body.model_dump(), timeout=5
        ).raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Демонстрационный источник недоступен") from exc
    db.add(AuditEntry(actor=operator.name, action="demo_scenario", comment=body.scenario))
    db.commit()
    return {"status": "ok", "detail": "Меняются только демонстрационные метрики"}

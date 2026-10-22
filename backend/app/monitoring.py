import hashlib
import json

import httpx
from sqlalchemy import select

from app.classifier import classify
from app.config import settings
from app.models import Incident, SourceState, utcnow


def fetch_alerts() -> list[dict]:
    config = settings()
    headers = {"Authorization": f"Bearer {config.prometheus_token}"} if config.prometheus_token else {}
    response = httpx.get(config.prometheus_url.rstrip("/") + "/api/v1/alerts", headers=headers, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success" or not isinstance(payload.get("data", {}).get("alerts"), list):
        raise ValueError("Prometheus вернул неверный формат ответа")
    return payload["data"]["alerts"]


def ingest_alerts(db, alerts: list[dict], source: str) -> list[str]:
    now = utcnow()
    active, changed = set(), []
    for alert in alerts:
        if alert.get("state") != "firing":
            continue
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        if not isinstance(labels, dict) or not isinstance(annotations, dict):
            raise ValueError("Некорректные метки события")
        external_id = hashlib.sha256(json.dumps(labels, sort_keys=True).encode()).hexdigest()
        active.add(external_id)
        item = db.scalar(select(Incident).where(Incident.source == source, Incident.external_id == external_id))
        title = str(annotations.get("summary") or labels.get("alertname") or "Событие мониторинга")
        description = str(annotations.get("description", ""))
        fresh = item is None
        if fresh:
            item = Incident(source=source, external_id=external_id, title=title)
            db.add(item)
        modified = fresh or item.title != title or item.description != description or item.labels != labels
        if item.lifecycle == "resolved":
            item.handling = "new"
            modified = True
        item.title, item.description, item.labels = title, description, labels
        item.host = str(labels.get("host") or labels.get("instance") or "unknown")[:255]
        item.lifecycle, item.recovered_at, item.last_seen = "firing", None, now
        if modified:
            for key, value in classify(dict(title=title, description=description, labels=labels)).items():
                setattr(item, key, value)
            item.recommendation_status = "pending"
            db.flush()
            changed.append(item.id)
    for item in db.scalars(select(Incident).where(Incident.source == source, Incident.lifecycle == "firing")):
        if item.external_id not in active:
            item.lifecycle, item.recovered_at = "resolved", now
    state = db.get(SourceState, source)
    if state is None:
        state = SourceState(id=source)
        db.add(state)
    state.last_success, state.last_attempt, state.error, state.count = now, now, "", len(active)
    db.commit()
    return changed

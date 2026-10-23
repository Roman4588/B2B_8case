import hashlib
import json
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.classifier import classify
from app.config import settings
from app.models import Incident, SourceState, uid, utcnow


def fingerprint(labels):
    return hashlib.sha256(json.dumps(labels, sort_keys=True).encode()).hexdigest()


def alert_start(alert, now):
    try:
        value = datetime.fromisoformat(str(alert.get("activeAt", "")).replace("Z", "+00:00"))
        if value.tzinfo is None or value > now:
            return None
        return value.astimezone(UTC)
    except ValueError:
        return None


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
    current = {
        fingerprint(item.labels): item
        for item in db.scalars(
            select(Incident).where(Incident.source == source, Incident.lifecycle == "firing")
        )
    }
    for alert in alerts:
        if alert.get("state") != "firing":
            continue
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        if not isinstance(labels, dict) or not isinstance(annotations, dict):
            raise ValueError("Некорректные метки события")
        key = fingerprint(labels)
        item = current.get(key)
        started = alert_start(alert, now)
        # A new activeAt also detects a recovery/reoccurrence between two polls.
        if item is not None and started and started > item.first_seen.replace(tzinfo=UTC):
            item.lifecycle, item.recovered_at = "resolved", started
            item = None
        title = str(annotations.get("summary") or labels.get("alertname") or "Событие мониторинга")
        description = str(annotations.get("description", ""))
        fresh = item is None
        if fresh:
            item = Incident(
                source=source,
                external_id=fingerprint({"labels": labels, "episode": uid()}),
                title=title,
                first_seen=started or now,
                recommendation_generation=0,
            )
            db.add(item)
            current[key] = item
        modified = fresh or item.title != title or item.description != description or item.labels != labels
        item.title, item.description, item.labels = title, description, labels
        item.host = str(labels.get("host") or labels.get("instance") or "unknown")[:255]
        item.lifecycle, item.recovered_at, item.last_seen = "firing", None, now
        if modified:
            for field, value in classify(dict(title=title, description=description, labels=labels)).items():
                setattr(item, field, value)
            item.recommendation_status = "pending"
            item.recommendations = []
            item.recommendation_generation += 1
            db.flush()
            changed.append(item.id)
        active.add(item.id)
    for item in db.scalars(select(Incident).where(Incident.source == source, Incident.lifecycle == "firing")):
        if item.id not in active:
            item.lifecycle, item.recovered_at = "resolved", now
    state = db.get(SourceState, source)
    if state is None:
        state = SourceState(id=source)
        db.add(state)
    state.last_success, state.last_attempt, state.error, state.count = now, now, "", len(active)
    db.commit()
    return changed

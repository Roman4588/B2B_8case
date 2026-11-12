"""Engineer decisions: automatic incident columns are never overwritten here."""

from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import AuditEntry, ClassificationCorrection, Incident, RecommendationFeedback, utcnow

FIELDS = ("severity", "category", "priority")


def effective(field):
    override = (
        select(getattr(ClassificationCorrection, field))
        .where(ClassificationCorrection.incident_id == Incident.id)
        .correlate(Incident)
        .scalar_subquery()
    )
    return func.coalesce(override, getattr(Incident, field))


def locked_incident(db, incident_id):
    # All feedback writers lock the parent before looking up the unique child.
    # Populate existing also handles sessions that loaded the row during auth/read.
    row = db.scalar(
        select(Incident)
        .where(Incident.id == incident_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "Событие не найдено")
    return row


def correction_values(row):
    return {key: getattr(row, key) for key in (*FIELDS, "comment")}


def save_correction(db, incident_id, operator, values):
    incident = locked_incident(db, incident_id)
    row = db.scalar(
        select(ClassificationCorrection).where(ClassificationCorrection.incident_id == incident_id)
    )
    if row is not None and correction_values(row) == values:
        db.commit()
        return incident
    before = (
        correction_values(row) if row else {**{key: getattr(incident, key) for key in FIELDS}, "comment": ""}
    )
    if row is None:
        row = ClassificationCorrection(incident_id=incident_id)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    row.operator_id, row.actor, row.updated_at = operator.id, operator.name, utcnow()
    row.input_snapshot = deepcopy(
        {"title": incident.title, "description": incident.description, "labels": incident.labels}
    )
    db.add(
        AuditEntry(
            actor=operator.name,
            operator_id=operator.id,
            action="classification_corrected",
            incident_id=incident_id,
            comment=f"{incident.title}: {before['severity']}/{before['category']}/{before['priority']} → {row.severity}/{row.category}/{row.priority}. {row.comment}",
            details={"before": before, "after": values},
        )
    )
    db.commit()
    return incident


def save_feedback(db, incident_id, runbook_id, operator, helpful, revision, generation):
    incident = locked_incident(db, incident_id)
    recommendation = next(
        (
            rec
            for rec in incident.recommendations
            if rec.get("id") == runbook_id and rec.get("revision") == revision
        ),
        None,
    )
    if (
        incident.recommendation_status != "ready"
        or incident.recommendation_generation != generation
        or recommendation is None
    ):
        raise HTTPException(409, "Рекомендация обновилась. Обновите карточку и оцените показанную редакцию")
    row = db.scalar(
        select(RecommendationFeedback).where(
            RecommendationFeedback.incident_id == incident_id,
            RecommendationFeedback.operator_id == operator.id,
            RecommendationFeedback.runbook_id == runbook_id,
            RecommendationFeedback.revision == revision,
        )
    )
    if row is not None and row.helpful == helpful:
        db.commit()
        return row
    before = row.helpful if row else None
    if row is None:
        row = RecommendationFeedback(
            incident_id=incident_id,
            operator_id=operator.id,
            runbook_id=runbook_id,
            revision=revision,
            recommendation_snapshot=deepcopy(recommendation),
        )
        db.add(row)
    row.helpful, row.actor, row.updated_at, row.generation = helpful, operator.name, utcnow(), generation
    db.add(
        AuditEntry(
            actor=operator.name,
            operator_id=operator.id,
            action="recommendation_feedback",
            incident_id=incident_id,
            comment=f"{incident.title} · {recommendation.get('title', runbook_id)} · ред. {revision}: {'Помогла' if helpful else 'Не помогла'}",
            details={
                "before": {"helpful": before},
                "after": {"helpful": helpful},
                "runbook_id": runbook_id,
                "revision": revision,
                "generation": generation,
            },
        )
    )
    db.commit()
    return row


def usefulness_counts(db):
    result = {}
    for book_id, helpful, count in db.execute(
        select(RecommendationFeedback.runbook_id, RecommendationFeedback.helpful, func.count()).group_by(
            RecommendationFeedback.runbook_id, RecommendationFeedback.helpful
        )
    ):
        result.setdefault(book_id, {"helpful_count": 0, "not_helpful_count": 0})[
            "helpful_count" if helpful else "not_helpful_count"
        ] = count
    return result

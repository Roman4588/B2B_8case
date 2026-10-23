import logging

from sqlalchemy import select, update

from app.models import Incident, Runbook


def invalidate_recommendations(db):
    db.execute(
        update(Incident)
        .where(Incident.lifecycle == "firing")
        .values(
            recommendation_status="pending",
            recommendations=[],
            recommendation_generation=Incident.recommendation_generation + 1,
        )
    )


def refresh_recommendations(db, incident_id, search):
    """Compute outside row locks and publish only if the request is still current."""
    item = db.get(Incident, incident_id, populate_existing=True)
    if item is None or item.lifecycle != "firing" or item.recommendation_status != "pending":
        return
    generation = item.recommendation_generation
    query = f"{item.title}. {item.description}"
    # Release the read transaction before running a potentially slow embedding model.
    db.commit()
    try:
        hits = search(db, query)
        status = "ready"
    except Exception:
        db.rollback()
        logging.getLogger(__name__).exception("Recommendation search failed: %s", incident_id)
        hits, status = [], "failed"
    db.execute(
        update(Incident)
        .where(
            Incident.id == incident_id,
            Incident.lifecycle == "firing",
            Incident.recommendation_status == "pending",
            Incident.recommendation_generation == generation,
        )
        .values(recommendations=hits, recommendation_status=status)
    )
    db.commit()


def has_ready_runbooks(db):
    return db.scalar(select(Runbook.id).where(Runbook.status == "ready").limit(1)) is not None

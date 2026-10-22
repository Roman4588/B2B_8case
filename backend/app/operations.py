from sqlalchemy import select

from app.models import AuditEntry, Incident


def manual_action(db, incident_id: str, action: str, actor: str, comment: str):
    incident = db.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
    if incident is None:
        raise LookupError("Событие не найдено")
    targets = {"accept": "accepted", "complete": "completed", "dismiss": "dismissed"}
    allowed = {"accept": {"new"}, "complete": {"accepted"}, "dismiss": {"new", "accepted"}}
    if action not in targets:
        raise ValueError("Неизвестное действие")
    if incident.handling == targets[action]:
        return incident
    if incident.handling not in allowed[action]:
        raise ValueError("Статус уже изменён. Обновите событие")
    incident.handling = targets[action]
    db.add(AuditEntry(actor=actor, action=action, incident_id=incident.id, comment=comment))
    db.commit()
    db.refresh(incident)
    return incident

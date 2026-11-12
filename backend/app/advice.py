"""Conservative display/search policy; does not change incident classification."""

import re

from sqlalchemy import select

from app.models import ClassificationCorrection

# Require a completed CHECK, rather than treating every info/P4 event as harmless.
COMPLETED_CHECK = re.compile(
    r"\b(?:health[ -]?check|проверка)\b[^.!?\n]{0,100}"
    r"\b(?:completed|succeeded|passed|завершена|пройдена)\b",
    re.I,
)
CONTRADICTION = re.compile(
    r"\b(?:not|never|no|cannot|не|нет|но|but|if|если|maybe|unknown|uncertain|"
    r"unsuccess\w*|fail\w*|error\w*|exception\w*|"
    r"неуспеш\w*|ошиб\w*|critical|warning\w*|down|unreachable|unavailable|outage|"
    r"high|low|full|timeout|latency|threshold|pressure|utilization|degraded)\b|"
    r"недоступ|отказ|авари|исчерпан|критич|предупрежд|порог|высок|заканчива|задержк|"
    r"проблем|сбо[йяи]|наруш|неизвест|возможно|безуспеш|\?",
    re.I,
)


def successful_check(values):
    text = f"{values['title']}. {values['description']}"
    return bool(
        values["lifecycle"] == "firing"
        and values["severity"] == "info"
        and values["priority"] == "P4"
        and not values["needs_review"]
        and COMPLETED_CHECK.search(text)
        and not CONTRADICTION.search(text)
    )


def effective_successful_check(db, item):
    values = {
        key: getattr(item, key)
        for key in ("title", "description", "lifecycle", "severity", "priority", "needs_review")
    }
    correction = db.scalar(
        select(ClassificationCorrection).where(ClassificationCorrection.incident_id == item.id)
    )
    if correction:
        values.update(severity=correction.severity, priority=correction.priority, needs_review=False)
    return successful_check(values)

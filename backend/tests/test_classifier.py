import pytest
from app.classifier import classify


@pytest.mark.parametrize(
    "event,want",
    [
        (
            {"title": "PostgreSQL primary is down", "labels": {"severity": "critical"}},
            ("critical", "database", "P1"),
        ),
        (
            {"title": "Заканчивается место на диске сервера", "labels": {"severity": "warning"}},
            ("warning", "server", "P3"),
        ),
        (
            {"title": "Packet loss on gateway", "labels": {"severity": "warning", "impact": "high"}},
            ("warning", "network", "P2"),
        ),
        (
            {"title": "Nginx deployment completed", "labels": {"severity": "info"}},
            ("info", "application", "P4"),
        ),
        ({"title": "Критический отказ репликации PostgreSQL"}, ("critical", "database", "P1")),
    ],
)
def test_event_classification(event, want):
    result = classify(event)
    assert (result["severity"], result["category"], result["priority"]) == want


def test_unrecognized_event_requires_human_review():
    result = classify({"title": "zzqvx 8821"})
    assert result["needs_review"] is True
    assert result["confidence"] < 0.65


def test_untrusted_label_cannot_inject_priority():
    result = classify({"title": "CPU utilization rising", "labels": {"priority": "P0", "category": "shell"}})
    assert result["priority"] in {"P1", "P2", "P3", "P4"}
    assert result["category"] in {"server", "network", "database", "application"}

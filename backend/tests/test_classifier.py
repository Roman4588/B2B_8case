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


@pytest.mark.parametrize(
    "title",
    [
        "PostgreSQL is down; backup completed successfully",
        "Не удалось восстановление сервера, сервис недоступен",
    ],
)
def test_success_of_another_operation_does_not_hide_outage(title):
    result = classify({"title": title})
    assert result["severity"] == "critical"
    assert result["priority"] == "P1"
    assert result["needs_review"]


@pytest.mark.parametrize(
    "title",
    [
        "PostgreSQL backup completed unsuccessfully",
        "Nginx was not restored",
        "Резервное копирование завершено неуспешно",
        "PostgreSQL has never been successfully restored",
        "Backup has not successfully completed",
        "PostgreSQL backup has not succeeded",
    ],
)
def test_failed_or_negated_success_is_not_informational(title):
    result = classify({"title": title})
    assert result["severity"] != "info"
    assert result["needs_review"]


def test_rule_score_is_not_an_invented_probability():
    result = classify({"title": "PostgreSQL is down"})
    assert "правило, не вероятность" in result["rationale"]
    assert result["confidence"] not in {0.9, 0.92}


def test_negated_outage_needs_review_instead_of_keyword_critical():
    result = classify({"title": "PostgreSQL is not down"})
    assert result["severity"] != "critical"
    assert result["needs_review"]
def test_complete_source_labels_do_not_load_text_model_dependencies():
    import subprocess
    import sys
    from pathlib import Path

    result = subprocess.run(
        [sys.executable, "-c", "import sys; from app.classifier import classify; "
         "result=classify({'labels': {'category': 'database', 'severity': 'critical'}}); "
         "assert result['priority'] == 'P1'; assert 'sklearn' not in sys.modules"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


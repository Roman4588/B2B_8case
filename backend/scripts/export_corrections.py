"""Export latest episode corrections, never training data or operator details."""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import session_factory  # noqa: E402
from app.models import ClassificationCorrection  # noqa: E402
from sqlalchemy import select  # noqa: E402

SAFE_LABELS = {"severity", "category", "impact"}


def redact(value):
    text = str(value)
    text = re.sub(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[REDACTED]", text, flags=re.S
    )
    text = re.sub(r"(?i)\b(?:bearer|basic)\s+\S+", "[REDACTED]", text)
    text = re.sub(
        r"""(?ix)\b(?:[\w-]*(?:password|passwd|pwd|secret|token|api[_-]?key|authorization|пароль|токен)[\w-]*)\b["']?\s*[:=]\s*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;]+)""",
        "[REDACTED]",
        text,
    )
    # Remove whole URIs before email masking, which could otherwise hide only
    # the tail of a password containing punctuation. URI schemes ignore case.
    text = re.sub(r"\b[a-z][a-z0-9+.-]*://\S+", "[REDACTED_URL]", text, flags=re.I)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[\w-]+", "[REDACTED_EMAIL]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[REDACTED]", text)
    return text


def export_examples(db):
    examples = []
    for correction in db.scalars(
        select(ClassificationCorrection).order_by(
            ClassificationCorrection.updated_at, ClassificationCorrection.id
        )
    ):
        snapshot = correction.input_snapshot
        # Allow only known classifier label values; arbitrary monitoring labels can contain secrets.
        allowed = {
            "severity": {
                "critical",
                "warning",
                "info",
                "disaster",
                "high",
                "average",
                "information",
                "informational",
            },
            "category": {"server", "network", "database", "application"},
            "impact": {"high", "normal"},
        }
        labels = {
            key: value
            for key, value in snapshot.get("labels", {}).items()
            if key in SAFE_LABELS and isinstance(value, str) and value in allowed[key]
        }
        examples.append(
            {
                "title": redact(snapshot.get("title", "")),
                "description": redact(snapshot.get("description", "")),
                "labels": labels,
                "severity": correction.severity,
                "category": correction.category,
                "priority": correction.priority,
                "provenance": {
                    "kind": "engineer_correction",
                    "episode_id": correction.incident_id,
                    "correction_id": correction.id,
                    "corrected_at": correction.updated_at.isoformat(),
                    "sanitized": True,
                },
            }
        )
    return examples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with session_factory()() as db:
        examples = export_examples(db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(examples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Экспортировано исправлений: {len(examples)}. Файл: {args.output}")

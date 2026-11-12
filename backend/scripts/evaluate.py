"""Frozen author-created benchmark; never used as training input."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent if (BACKEND.parent / "datasets").exists() else BACKEND
sys.path.insert(0, str(BACKEND))

from app.classifier import classify  # noqa: E402


def evaluate(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Корпус должен быть JSON-массивом событий")
    if not data:
        return {
            "samples": 0,
            "metrics": {},
            "confusion_matrices": {},
            "passed": None,
            "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "evaluated_at": datetime.now(UTC).isoformat(),
            "limitation": "Корпус пуст: метрики не рассчитаны.",
        }
    predictions = [classify(event) for event in data]
    fields = ("severity", "category", "priority")
    metrics = {
        field: sum(p[field] == e[field] for p, e in zip(predictions, data)) / len(data) for field in fields
    }
    metrics["triple_accuracy"] = sum(
        all(p[k] == e[k] for k in fields) for p, e in zip(predictions, data)
    ) / len(data)
    matrices = {}
    for field in fields:
        labels = sorted({event[field] for event in data} | {prediction[field] for prediction in predictions})
        matrices[field] = {
            a: {b: sum(e[field] == a and p[field] == b for e, p in zip(data, predictions)) for b in labels}
            for a in labels
        }
    return {
        "samples": len(data),
        "metrics": metrics,
        "confusion_matrices": matrices,
        "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "evaluated_at": datetime.now(UTC).isoformat(),
        "provenance": "Engineer corrections (sanitized input snapshots)."
        if all(event.get("provenance", {}).get("kind") == "engineer_correction" for event in data)
        else "Supplied evaluation corpus; separate from training.json.",
        "limitation": "Correction examples are selected errors, not an unbiased benchmark. Sanitization may change classifier input; accuracy on unknown events is unmeasured.",
        "passed": metrics["triple_accuracy"] >= 0.9,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets" / "evaluation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "classification-report.json")
    args = parser.parse_args()
    result = evaluate(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({"samples": result["samples"], **result["metrics"], "passed": result["passed"]}, indent=2)
    )
    if not result["samples"]:
        print(result["limitation"])
    sys.exit(0 if result["passed"] is not False else 1)

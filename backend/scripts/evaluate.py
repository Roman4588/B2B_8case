"""Frozen author-created benchmark; never used as training input."""
import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" if (ROOT / "backend").exists() else ROOT))

from app.classifier import classify  # noqa: E402


def evaluate(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    predictions = [classify(event) for event in data]
    fields = ("severity", "category", "priority")
    metrics = {field: sum(p[field] == e[field] for p, e in zip(predictions, data)) / len(data) for field in fields}
    metrics["triple_accuracy"] = sum(all(p[k] == e[k] for k in fields)
                                     for p, e in zip(predictions, data)) / len(data)
    matrices = {}
    for field in fields:
        labels = sorted({event[field] for event in data})
        matrices[field] = {a: {b: sum(e[field] == a and p[field] == b for e, p in zip(data, predictions))
                               for b in labels} for a in labels}
    return {"samples": len(data), "metrics": metrics, "confusion_matrices": matrices,
            "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "evaluated_at": datetime.now(UTC).isoformat(),
            "provenance": "Author-created Russian/English monitoring scenarios, separate from training.json.",
            "limitation": "Not an independent organizer benchmark; accuracy on unknown events is unmeasured.",
            "passed": metrics["triple_accuracy"] >= 0.9}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets" / "evaluation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "classification-report.json")
    args = parser.parse_args()
    result = evaluate(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": result["samples"], **result["metrics"], "passed": result["passed"]}, indent=2))
    sys.exit(0 if result["passed"] else 1)

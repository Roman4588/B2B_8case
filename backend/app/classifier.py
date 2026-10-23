"""Hybrid classifier: normalized source labels, documented rules and trained text fallback.

No evaluation data is loaded here. The small local text model is fitted from training.json only.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

CATEGORIES = ("server", "network", "database", "application")
SEVERITIES = ("critical", "warning", "info")
CATEGORY_PATTERNS = {
    "database": r"postgres|mysql|mongodb|redis|database|баз[аыуе]|реплика|replica|deadlock|vacuum|sql",
    "network": r"network|packet|gateway|router|switch|firewall|\bdns\b|\bbgp\b|\bvpn\b|uplink|сете|сет[ьи]|пакет|маршрут|коммутатор",
    "application": r"nginx|http|api\b|applicat|приложен|служб|сервис|deploy|container|kubernetes|\bpod\b|crashloop|certificate",
    "server": r"\bcpu\b|\bram\b|memory|disk|filesystem|inode|server|host|сервер|диск|памят|процессор|температур",
}
INFO = r"\b(?:completed|finished|succeeded|successfully|restored|resolved|восстановлен\w*|заверш[её]н\w*|успешн\w*)\b"
FAILED = r"\b(?:unsuccess\w*|failed|failure|неуспеш\w*)\b|не\s+удал\w*"
NEGATED_SUCCESS = r"\b(?:not|never|не)\s+(?:(?:been|был[аои]?)\s+)?(?:restored|resolved|completed|finished|восстанов\w*|заверш\w*|успеш\w*)"
NEGATED_CRITICAL = r"\b(?:not|no|without|не|нет)\s+(?:critical|down|unreachable|unavailable|outage|критич\w*|отказ\w*|авари\w*)\b"
CRITICAL = (
    r"critical|критич|недоступ|отказ|авари|исчерпан|\bdown\b|unreachable|unavailable|exhaust|crashloop|outage"
)
WARNING = r"warning|предупрежд|threshold|порог|elevated|rising|pressure|increas|высок|заканчива|задержк|approach|latency|utilization"


@lru_cache
def text_models():
    data = json.loads((Path(__file__).parent / "seed" / "training.json").read_text(encoding="utf-8"))
    models = {}
    for field, groups in data.items():
        texts, labels = [], []
        for label, examples in groups.items():
            texts.extend(examples)
            labels.extend([label] * len(examples))
        model = make_pipeline(
            TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)),
            LogisticRegression(C=8, max_iter=500, random_state=42),
        )
        model.fit(texts, labels)
        models[field] = model
    return models


def predict(field: str, text: str):
    model = text_models()[field]
    probabilities = model.predict_proba([text])[0]
    index = int(probabilities.argmax())
    return str(model.classes_[index]), float(probabilities[index])


def classify(event: dict) -> dict:
    text = f"{event.get('title', '')} {event.get('description', '')}".lower()
    labels = event.get("labels") or {}
    reasons = []
    review = False
    category = labels.get("category")
    if category in CATEGORIES:
        category_conf = 1.0
        reasons.append("Категория из метки мониторинга")
    else:
        category, category_conf = predict("category", text)
        matches = [name for name, pattern in CATEGORY_PATTERNS.items() if re.search(pattern, text)]
        if matches:
            category = matches[0]
            review = len(matches) > 1
            reasons.append("Категория по терминологии события (правило, не вероятность)")
        if len(matches) > 1:
            reasons.append("Упомянуты разные категории: нужна проверка инженера")
    severity = str(labels.get("severity", "")).lower()
    severity = {
        "disaster": "critical",
        "high": "critical",
        "average": "warning",
        "information": "info",
        "informational": "info",
    }.get(severity, severity)
    if severity in SEVERITIES:
        severity_conf = 1.0
        reasons.append("Тип из severity источника")
    else:
        severity, severity_conf = predict("severity", text)
        failed = bool(re.search(FAILED, text) or re.search(NEGATED_SUCCESS, text))
        severity_text = re.sub(NEGATED_CRITICAL, "", text)
        negated_critical = severity_text != text
        review |= negated_critical
        for name, pattern in (("critical", CRITICAL), ("warning", WARNING), ("info", INFO)):
            if re.search(pattern, severity_text):
                severity = "warning" if name == "info" and failed else name
                review |= failed or (name != "info" and bool(re.search(INFO, text)))
                reasons.append("Тип по формулировке события (правило, не вероятность)")
                break
        if failed and severity == "info":
            severity, review = "warning", True
        if negated_critical and severity == "critical" and not re.search(CRITICAL, severity_text):
            severity = "warning"
    priority = {"critical": "P1", "warning": "P3", "info": "P4"}[severity]
    if severity == "warning" and labels.get("impact") == "high":
        priority = "P2"
    reasons.append(f"Политика приоритета: {severity}, impact={labels.get('impact', 'normal')} → {priority}")
    confidence = round(min(category_conf, severity_conf), 4)
    return dict(
        severity=severity,
        category=category,
        priority=priority,
        confidence=confidence,
        needs_review=review or confidence < 0.65,
        rationale=". ".join(reasons),
    )

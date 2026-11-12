import { ThumbsUp, ThumbsDown, Check } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "./api";
import type { Feedback, Incident, Recommendation } from "./types";
import { categoryNames, time } from "./ui";

export function ClassificationEditor({
  item,
  onSaved,
}: {
  item: Incident;
  onSaved: (item: Incident) => void;
}) {
  const [editing, setEditing] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const closeEditor = () => {
    setEditing(false);
    requestAnimationFrame(() => toggle.current?.focus({ preventScroll: true }));
  };
  const [draft, setDraft] = useState({
    severity: item.severity,
    category: item.category,
    priority: item.priority,
    comment: item.classification_correction?.comment || "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    setBusy(true);
    setError("");
    try {
      const updated = await api<Incident>(
        `/incidents/${item.id}/classification`,
        { method: "PUT", body: JSON.stringify(draft) },
      );
      onSaved(updated);
      closeEditor();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!editing)
    return (
      <button
        ref={toggle}
        className="secondary classification-edit-toggle"
        aria-expanded={false}
        onClick={() => {
          setDraft({
            severity: item.severity,
            category: item.category,
            priority: item.priority,
            comment: item.classification_correction?.comment || "",
          });
          setError("");
          setEditing(true);
        }}
      >
        Исправить классификацию
      </button>
    );
  return (
    <form
      className="feedback-form"
      aria-label="Исправление классификации"
      aria-busy={busy}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          if (!busy) closeEditor();
        }
      }}
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <h3>Исправление классификации</h3>
      <label>
        Исправленный тип
        <select
          autoFocus
          value={draft.severity}
          onChange={(e) =>
            setDraft({
              ...draft,
              severity: e.target.value as Incident["severity"],
            })
          }
        >
          <option value="critical">Критическое</option>
          <option value="warning">Предупреждение</option>
          <option value="info">Информационное</option>
        </select>
      </label>
      <label>
        Исправленная категория
        <select
          value={draft.category}
          onChange={(e) =>
            setDraft({
              ...draft,
              category: e.target.value as Incident["category"],
            })
          }
        >
          {Object.entries(categoryNames).map(([value, label]) => (
            <option value={value} key={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Исправленный приоритет
        <select
          value={draft.priority}
          onChange={(e) => setDraft({ ...draft, priority: e.target.value })}
        >
          {["P1", "P2", "P3", "P4"].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <label>
        Комментарий к классификации
        <textarea
          maxLength={2000}
          value={draft.comment}
          onChange={(e) => setDraft({ ...draft, comment: e.target.value })}
        />
      </label>
      {error && (
        <div className="error" role="alert">
          {error} Повторите сохранение.
        </div>
      )}
      <div className="actions">
        <button className="primary" disabled={busy}>
          {busy ? "Сохраняем…" : "Сохранить классификацию"}
        </button>
        <button
          type="button"
          className="secondary"
          disabled={busy}
          onClick={closeEditor}
        >
          Отмена
        </button>
      </div>
    </form>
  );
}

export function RecommendationRating({
  incidentId,
  rec,
  generation,
  onSaved,
}: {
  incidentId: string;
  rec: Recommendation;
  generation: number;
  onSaved: (feedback: Feedback) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(true);
  async function save(helpful: boolean) {
    setAttempt(helpful);
    setBusy(true);
    setError("");
    try {
      const feedback = await api<Feedback>(
        `/incidents/${incidentId}/recommendations/${rec.id}/feedback`,
        {
          method: "PUT",
          body: JSON.stringify({ helpful, revision: rec.revision, generation }),
        },
      );
      onSaved(feedback);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="recommendation-rating" aria-busy={busy}>
      <p>Помогла ли инструкция?</p>
      <div className="actions">
        {[true, false].map((helpful) => (
          <button
            key={String(helpful)}
            className="secondary"
            disabled={busy}
            aria-pressed={rec.feedback?.helpful === helpful}
            onClick={() => void save(helpful)}
          >
            {rec.feedback?.helpful === helpful ? (
              <Check size={15} aria-hidden="true" />
            ) : helpful ? (
              <ThumbsUp size={15} aria-hidden="true" />
            ) : (
              <ThumbsDown size={15} aria-hidden="true" />
            )}
            {helpful ? "Помогла" : "Не помогла"}
          </button>
        ))}
      </div>
      {busy && <small role="status">Сохраняем оценку…</small>}
      <small>Оценка не меняет состояние события.</small>
      {rec.feedback && (
        <small>
          {rec.feedback.actor} · {time(rec.feedback.updated_at)}
        </small>
      )}
      {error && (
        <div className="error" role="alert">
          {error}
          <button disabled={busy} onClick={() => void save(attempt)}>
            Повторить оценку
          </button>
        </div>
      )}
    </div>
  );
}

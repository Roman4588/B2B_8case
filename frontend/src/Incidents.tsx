import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Copy,
  Filter,
  Search,
  ClipboardList,
  RefreshCw,
  X,
} from "lucide-react";
import { api, useResource } from "./api";
import { ClassificationEditor, RecommendationRating } from "./EngineerFeedback";
import type { Audit, Incident } from "./types";
import {
  actionNames,
  categoryIcons,
  categoryNames,
  Empty,
  handlingNames,
  SeverityBadge,
  time,
} from "./ui";

export function Incidents({ onChanged }: { onChanged: () => void }) {
  const [q, setQ] = useState("");
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [state, setState] = useState("firing");
  const [priority, setPriority] = useState("");
  const [handling, setHandling] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const selectedRow = useRef<HTMLButtonElement | null>(null);
  const detailPanel = useRef<HTMLElement | null>(null);
  const closeDetail = () => {
    setSelected(null);
    selectedRow.current?.focus({ preventScroll: true });
  };
  useEffect(() => {
    if (!selected) return;
    const narrow = window.matchMedia("(max-width: 1100px)");
    const syncLock = () =>
      document.body.classList.toggle("incident-overlay-open", narrow.matches);
    syncLock();
    narrow.addEventListener("change", syncLock);
    detailPanel.current?.focus({ preventScroll: true });
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Tab" && narrow.matches && detailPanel.current) {
        const controls = Array.from(
          detailPanel.current.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
          ),
        ).filter((element) => element.getClientRects().length > 0);
        const first = controls[0];
        const last = controls.at(-1);
        const active = document.activeElement;
        if (
          event.shiftKey &&
          (active === first || active === detailPanel.current)
        ) {
          event.preventDefault();
          last?.focus();
        } else if (
          !event.shiftKey &&
          (active === last || !detailPanel.current.contains(active))
        ) {
          event.preventDefault();
          first?.focus();
        }
      }
      if (event.key === "Escape" && !event.defaultPrevented) {
        setSelected(null);
        selectedRow.current?.focus({ preventScroll: true });
      }
    };
    window.addEventListener("keydown", escape);
    return () => {
      document.body.classList.remove("incident-overlay-open");
      narrow.removeEventListener("change", syncLock);
      window.removeEventListener("keydown", escape);
    };
  }, [selected]);
  const params = new URLSearchParams({
    q,
    severity,
    category,
    state,
    priority,
    handling,
    page: String(page),
  });
  const { data, error, refresh } = useResource<{
    items: Incident[];
    total: number;
  }>("/incidents?" + params);
  useEffect(() => {
    setPage(1);
  }, [q, severity, category, state, priority, handling]);
  const items = data?.items || [];
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>
            Лента событий <span className="count">{data?.total ?? "—"}</span>
          </h2>
        </div>
        <span className="live-label">
          <RefreshCw size={13} aria-hidden="true" />
          Обновление каждые 5 сек
        </span>
      </div>
      <div className="workspace">
        <section className="event-panel">
          <div className="filters">
            <label className="search">
              <Search size={17} />
              <input
                aria-label="Поиск событий"
                placeholder="Событие или хост…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </label>
            <div className="filter-row">
              <Filter size={15} />
              <select
                aria-label="Тип события"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                <option value="">Все типы</option>
                <option value="critical">Критические</option>
                <option value="warning">Предупреждения</option>
                <option value="info">Информационные</option>
              </select>
              <select
                aria-label="Приоритет"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option value="">Все приоритеты</option>
                {["P1", "P2", "P3", "P4"].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
              <select
                aria-label="Статус обработки"
                value={handling}
                onChange={(e) => setHandling(e.target.value)}
              >
                <option value="">Вся работа</option>
                {Object.entries(handlingNames).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
              <select
                aria-label="Категория"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">Все категории</option>
                {Object.entries(categoryNames).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
              <select
                aria-label="Состояние событий"
                value={state}
                onChange={(e) => setState(e.target.value)}
              >
                <option value="firing">Активные</option>
                <option value="resolved">Восстановленные</option>
                <option value="">Все события</option>
              </select>
            </div>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
              <button onClick={refresh}>Повторить</button>
            </div>
          )}
          {!data && !error && (
            <div className="loading event-loading" role="status">
              Получаем события…
              <div className="event-skeleton" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}
          {data && items.length === 0 && (
            <Empty
              title="Здесь спокойно"
              description="Событий по выбранным условиям нет. Измените фильтры или дождитесь обновления мониторинга."
            />
          )}
          <div className="event-list">
            {items.map((item) => {
              const Icon = categoryIcons[item.category];
              return (
                <button
                  className={
                    "event-row " + (selected === item.id ? "selected" : "")
                  }
                  key={item.id}
                  data-incident-id={item.id}
                  aria-pressed={selected === item.id}
                  onClick={(event) => {
                    selectedRow.current = event.currentTarget;
                    setSelected(item.id);
                  }}
                >
                  <span className="event-content">
                    <span className="event-top">
                      <SeverityBadge value={item.severity} />
                      <span
                        className={"priority " + item.priority.toLowerCase()}
                      >
                        {item.priority}
                      </span>
                      <time>{time(item.first_seen)}</time>
                    </span>
                    <strong>{item.title}</strong>
                    {item.classification_correction && (
                      <small className="correction-marker">
                        Исправлено инженером:{" "}
                        {item.classification_correction.actor},{" "}
                        {time(item.classification_correction.updated_at)}
                      </small>
                    )}
                    <span className="event-meta">
                      <span>
                        <Icon size={13} />
                        {item.host}
                      </span>
                      <span>{categoryNames[item.category]}</span>
                      <span className={"handling " + item.handling}>
                        {handlingNames[item.handling]}
                      </span>
                    </span>
                  </span>
                  <ChevronRight size={17} />
                </button>
              );
            })}
          </div>
          {data && data.total > 50 && (
            <div className="pagination">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Назад
              </button>
              <span>Страница {page}</span>
              <button
                disabled={page * 50 >= data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Далее
              </button>
            </div>
          )}
        </section>
        <aside
          ref={detailPanel}
          tabIndex={-1}
          aria-label="Карточка события"
          className={"detail-panel " + (selected ? "has-selection" : "")}
        >
          {selected ? (
            <Detail
              key={selected}
              id={selected}
              onClose={closeDetail}
              onChanged={() => {
                refresh();
                onChanged();
              }}
            />
          ) : (
            <div className="detail-placeholder">
              <ClipboardList size={24} aria-hidden="true" />
              <h3>Выберите событие</h3>
              <p>
                Выберите событие, чтобы увидеть разбор и подходящие инструкции.
              </p>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}

function Detail({
  id,
  onClose,
  onChanged,
}: {
  id: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const {
    data: item,
    error,
    refresh,
    update,
  } = useResource<Incident>("/incidents/" + id);
  const history = useResource<Audit[]>("/incidents/" + id + "/history");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    setComment("");
    setMessage("");
  }, [id]);
  async function action(name: string) {
    setBusy(true);
    setMessage("");
    try {
      await api("/incidents/" + id + "/actions", {
        method: "POST",
        body: JSON.stringify({ action: name, comment }),
      });
      refresh();
      history.refresh();
      onChanged();
      setMessage("Решение записано. Инфраструктурные команды не запускались.");
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function copy(steps: string[]) {
    try {
      await navigator.clipboard.writeText(
        steps.map((s, i) => `${i + 1}. ${s}`).join("\n"),
      );
      setCopied(true);
    } catch {
      setMessage("Копирование недоступно. Выделите текст инструкции вручную.");
    }
  }
  if (error && !item)
    return (
      <div className="error" role="alert">
        {error}
        <button onClick={refresh}>Повторить</button>
      </div>
    );
  if (!item) return <div className="loading">Разбираем событие…</div>;
  return (
    <div className="detail-content incident-detail">
      {error && (
        <div className="error incident-refresh-error" role="alert">
          <span>{error}</span>
          <button onClick={refresh}>Повторить обновление</button>
        </div>
      )}
      <div className="detail-toolbar">
        <span>
          <ClipboardList size={15} /> Разбор события
        </span>
        <button
          aria-label="Закрыть событие"
          className="icon-button"
          onClick={onClose}
        >
          <X size={19} />
        </button>
      </div>
      <div
        className="detail-title"
        tabIndex={0}
        role="region"
        aria-label="Сведения о событии"
      >
        <SeverityBadge value={item.severity} />
        <h2>{item.title}</h2>
        <div className="detail-facts">
          <span>
            Хост<strong>{item.host}</strong>
          </span>
          <span>
            Категория<strong>{categoryNames[item.category]}</strong>
          </span>
          <span>
            Приоритет<strong>{item.priority}</strong>
          </span>
          <span>
            Состояние
            <strong>
              {item.lifecycle === "firing" ? "Активно" : "Восстановлено"}
            </strong>
          </span>
        </div>
      </div>
      <div
        className="incident-reading"
        role="region"
        aria-label="Разбор и рекомендации"
        tabIndex={0}
      >
        <p className="incident-description">{item.description}</p>
        <div className="classification-note">
          {item.classification_correction && (
            <div className="classification-correction">
              <strong>Исправлено инженером</strong>
              <span>
                {item.classification_correction.actor},{" "}
                {time(item.classification_correction.updated_at)}
              </span>
            </div>
          )}
          <details className="classification-explanation">
            <summary>
              {item.classification_correction
                ? "Автоматическая классификация отдельно"
                : "Обоснование классификации"}
            </summary>
            <p>{item.automatic_classification?.rationale || item.rationale}</p>
            {item.classification_correction &&
              item.automatic_classification && (
                <>
                  <p>
                    {item.automatic_classification.severity} ·{" "}
                    {categoryNames[item.automatic_classification.category]} ·{" "}
                    {item.automatic_classification.priority}
                  </p>
                  <p>
                    Уверенность автоматической модели:{" "}
                    {item.automatic_classification.confidence}. Она не относится
                    к ручному решению.
                  </p>
                </>
              )}
          </details>
          <span className={"confidence " + (item.needs_review ? "low" : "")}>
            {item.classification_correction
              ? "Решение инженера"
              : item.needs_review
                ? "Нужна ручная проверка"
                : "Автоматический разбор"}
          </span>
          <small>Проверьте вывод перед выполнением действий.</small>
          <ClassificationEditor
            item={item}
            onSaved={(updated) => {
              update((current) => {
                if (
                  current.classification_correction &&
                  updated.classification_correction &&
                  current.classification_correction.updated_at >
                    updated.classification_correction.updated_at
                )
                  return current;
                return {
                  ...current,
                  severity: updated.severity,
                  category: updated.category,
                  priority: updated.priority,
                  confidence: updated.confidence,
                  needs_review: updated.needs_review,
                  rationale: updated.rationale,
                  classification_correction: updated.classification_correction,
                };
              });
              refresh();
              history.refresh();
              onChanged();
            }}
          />
        </div>
        <div className="recommendation-heading">
          <h3>
            <ClipboardList size={17} /> Рекомендации
          </h3>
          <span>
            {item.recommendation_status === "ready"
              ? item.recommendations.length
              : "—"}
          </span>
        </div>
        {item.lifecycle === "resolved" && (
          <div className="hint">
            Событие снято.{" "}
            {item.recommendations.length
              ? "Сохранённые рекомендации показаны как история."
              : "Сохранённых рекомендаций нет."}
          </div>
        )}
        {item.lifecycle === "firing" &&
          item.recommendation_status === "not_required" && (
            <div className="hint">
              Вмешательство не требуется: проверка завершена успешно.
            </div>
          )}
        {item.lifecycle === "firing" &&
          item.recommendation_status === "pending" && (
            <div className="hint">
              Ищем подходящие регламенты. При первом запуске загружается
              локальная модель.
            </div>
          )}
        {item.lifecycle === "firing" &&
          item.recommendation_status === "ready" &&
          !item.recommendations.length && (
            <div className="hint">
              Регламент не найден. Проверьте событие вручную или добавьте
              регламент в базу знаний.
            </div>
          )}
        {item.lifecycle === "firing" &&
          item.recommendation_status === "failed" && (
            <div className="error" role="alert">
              Не удалось подобрать инструкции. Проверьте событие вручную или
              повторите поиск.
              <button
                disabled={busy || item.lifecycle !== "firing"}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api("/incidents/" + id + "/recommendations/retry", {
                      method: "POST",
                    });
                    refresh();
                  } catch (err) {
                    setMessage((err as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Повторить поиск
              </button>
            </div>
          )}
        {(item.recommendation_status === "ready"
          ? item.recommendations
          : []
        ).map((rec, index) => (
          <article
            className="recommendation"
            key={`${rec.id}:${rec.revision}:${item.recommendation_generation}`}
          >
            <h4>{rec.title}</h4>
            <div className="rec-top">
              <span>
                {index === 0 ? "Лучшее совпадение" : "Похожий регламент"}
              </span>
              <span>{Math.round(rec.similarity * 100)}% сходства</span>
            </div>
            <div className="recommendation-explanation">
              <p>Условие: {rec.condition}</p>
              <p>
                {rec.matched_terms?.length
                  ? `Совпавшие слова: ${rec.matched_terms.join(", ")}`
                  : "Прямых совпадений содержательных слов нет."}
              </p>
              <small>
                {rec.explanation ||
                  "Сходство текстов не является вероятностью правильности рекомендации."}
              </small>
            </div>
            <ol>
              {rec.steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
            {rec.cautions && <div className="caution">{rec.cautions}</div>}
            <footer>
              <span>
                Источник: {rec.source}
                <br />
                Редакция {rec.revision}
              </span>
              <button
                className="icon-button"
                aria-label="Скопировать инструкцию"
                onClick={() => void copy(rec.steps)}
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
              </button>
            </footer>
            <RecommendationRating
              incidentId={id}
              rec={rec}
              generation={item.recommendation_generation}
              onSaved={(feedback) => {
                update((current) =>
                  current.recommendation_generation !==
                  item.recommendation_generation
                    ? current
                    : {
                        ...current,
                        recommendations: current.recommendations.map((value) =>
                          value.id === rec.id &&
                          value.revision === rec.revision &&
                          (!value.feedback ||
                            Date.parse(value.feedback.updated_at) <=
                              Date.parse(feedback.updated_at))
                            ? { ...value, feedback }
                            : value,
                        ),
                      },
                );
                refresh();
                history.refresh();
              }}
            />
          </article>
        ))}
        <section className="incident-history" aria-label="История решений">
          <h3>История решений</h3>
          <p>Действия инженера по этому эпизоду аварии</p>
          {history.error && (
            <div className="error" role="alert">
              {history.error}
            </div>
          )}
          {!history.data && !history.error && (
            <p role="status">Загружаем историю…</p>
          )}
          {history.data?.length === 0 && <p>Решений пока нет.</p>}
          <ol>
            {history.data?.map((entry) => (
              <li key={entry.id}>
                <strong>{actionNames[entry.action] || entry.action}</strong>
                <span>
                  {entry.actor}
                  <br />
                  {time(entry.created_at)}
                </span>
                {entry.comment && <blockquote>{entry.comment}</blockquote>}
              </li>
            ))}
          </ol>
        </section>
        <button className="back-link" onClick={onClose}>
          <ArrowLeft size={14} /> К списку событий
        </button>
      </div>
      <div className="manual-controls">
        <div className="decision-heading">
          <h3>Решение инженера</h3>
          <p className="current-state">{handlingNames[item.handling]}</p>
        </div>
        <label className="decision-comment">
          <span>Комментарий</span>
          <textarea
            rows={1}
            placeholder="Что проверили или планируете сделать…"
            maxLength={2000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </label>
        <div className="actions">
          {item.handling === "new" && (
            <button
              className="primary"
              disabled={busy}
              onClick={() => void action("accept")}
            >
              <Check size={16} />
              Принято к ручному выполнению
            </button>
          )}
          {item.handling === "accepted" && (
            <button
              className="primary"
              disabled={busy}
              onClick={() => void action("complete")}
            >
              <Check size={16} />
              Выполнено вручную
            </button>
          )}
          {["new", "accepted"].includes(item.handling) && (
            <button
              className="secondary"
              disabled={busy}
              onClick={() => void action("dismiss")}
            >
              Отклонить
            </button>
          )}
        </div>
        {message && (
          <div className="hint" role="status">
            {message}
          </div>
        )}
      </div>
    </div>
  );
}

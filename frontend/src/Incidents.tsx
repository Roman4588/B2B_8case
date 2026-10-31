import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Copy,
  Filter,
  Search,
  ShieldCheck,
  ClipboardList,
  RefreshCw,
  X,
} from "lucide-react";
import { api, useResource } from "./api";
import type { Audit, Incident } from "./types";
import {
  actionNames,
  categoryIcons,
  categoryNames,
  Empty,
  handlingNames,
  SafetyNote,
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
                  aria-pressed={selected === item.id}
                  onClick={() => setSelected(item.id)}
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
          <div className="panel-footer">
            <span>
              <ShieldCheck size={14} /> Ни одно действие не выполняется
              автоматически
            </span>
          </div>
        </section>
        <aside className={"detail-panel " + (selected ? "has-selection" : "")}>
          {selected ? (
            <Detail
              key={selected}
              id={selected}
              onClose={() => setSelected(null)}
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
  if (error) return <div className="error">{error}</div>;
  if (!item) return <div className="loading">Разбираем событие…</div>;
  return (
    <div className="detail-content incident-detail">
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
      <div className="detail-title">
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
        <div className="classification-note">
          <details className="classification-explanation">
            <summary>Обоснование классификации</summary>
            <p>{item.rationale}</p>
          </details>
          <span className={"confidence " + (item.needs_review ? "low" : "")}>
            {item.needs_review
              ? "Нужна ручная проверка"
              : "Автоматический разбор"}
          </span>
          <small>Проверьте вывод перед выполнением действий.</small>
        </div>
        <p className="incident-description">{item.description}</p>
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
        {item.recommendation_status === "pending" && (
          <div className="hint">
            Ищем подходящие регламенты. При первом запуске загружается локальная
            модель.
          </div>
        )}
        {item.recommendation_status === "ready" &&
          !item.recommendations.length && (
            <div className="hint">
              Близких инструкций нет. Проверьте событие вручную или добавьте
              регламент в базу знаний.
            </div>
          )}
        {item.recommendation_status === "failed" && (
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
          <article className="recommendation" key={rec.id}>
            <h4>{rec.title}</h4>
            <div className="rec-top">
              <span>
                {index === 0 ? "Лучшее совпадение" : "Похожий регламент"}
              </span>
              <span>{Math.round(rec.similarity * 100)}% сходства</span>
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
        <SafetyNote />
      </div>
    </div>
  );
}

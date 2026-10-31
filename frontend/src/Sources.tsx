import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { api, useResource } from "./api";
import type { Source } from "./types";
import { sourceStatusNames, time } from "./ui";

export function Sources() {
  const { data, error, refresh } = useResource<Source>("/sources");
  const readiness = useResource<{ status: string; indexed_runbooks: number }>(
    "/health/ready",
    10000,
  );
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  async function sync() {
    setBusy(true);
    try {
      await api("/sources/sync", { method: "POST" });
      setNotice(
        "Проверка источника добавлена в очередь. Состояние обновится автоматически.",
      );
      refresh();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function scenario(value: string) {
    try {
      await api("/demo", {
        method: "POST",
        body: JSON.stringify({ scenario: value }),
      });
      setNotice(
        "Демонстрационные метрики изменены. События обновятся в течение 30 секунд.",
      );
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  return (
    <div className="sources-workspace">
      {error && <div className="error">{error}</div>}
      {readiness.error ? (
        <div className="error" role="alert">
          Не удалось проверить базу знаний.
        </div>
      ) : readiness.data?.status === "ready" ? (
        <p className="knowledge-count">
          Инструкций в базе: <strong>{readiness.data.indexed_runbooks}</strong>
        </p>
      ) : (
        <p className="subtle" role="status">
          База знаний подготавливается…
        </p>
      )}
      <section className="source-card">
        <header>
          <div>
            <h2>Prometheus</h2>
            <p>
              События через официальный{" "}
              <abbr title="Программный интерфейс по протоколу HTTP">
                HTTP API
              </abbr>
            </p>
          </div>
          <span
            className={
              "connection " +
              (!error && data?.status === "online" ? "online" : "offline")
            }
          >
            {error
              ? "Нет связи с приложением"
              : sourceStatusNames[data?.status || "waiting"]}
          </span>
        </header>
        <div className="source-facts">
          <span>
            Последняя синхронизация
            <strong>{time(data?.state?.last_success)}</strong>
          </span>
          <span>
            Активных событий<strong>{data?.state?.count ?? "—"}</strong>
          </span>
          <span>
            Период опроса<strong>{data?.interval_seconds || 15} секунд</strong>
          </span>
        </div>
        {data?.state?.error && <div className="error">{data.state.error}</div>}
        {data?.status === "stale" && (
          <div className="error" role="alert">
            Новые данные не поступают больше минуты. Показанные события могут
            быть устаревшими. Проверьте подключение и работу фонового
            обработчика.
          </div>
        )}
        <footer>
          <span>Повторные события объединяются автоматически</span>
          <button
            className="secondary"
            disabled={busy}
            onClick={() => void sync()}
          >
            <RefreshCw size={15} />
            Проверить подключение
          </button>
        </footer>
      </section>
      {data?.demo_mode && (
        <section className="demo-card">
          <h2>Учебный стенд</h2>
          <p>
            Выберите состояние учебной инфраструктуры. Настоящий Prometheus
            обнаружит изменение метрик и передаст события ассистенту.
          </p>
          <div className="scenario-buttons">
            <button
              className="secondary"
              onClick={() => void scenario("outage")}
            >
              Аварийные события
            </button>
            <button
              className="secondary"
              onClick={() => void scenario("warning")}
            >
              Предупреждения
            </button>
            <button
              className="secondary"
              onClick={() => void scenario("normal")}
            >
              Восстановление
            </button>
          </div>
          <small>
            Меняются только синтетические метрики. Рабочие службы и реальные
            серверы не затрагиваются.
          </small>
        </section>
      )}
      {notice && (
        <div className="hint" role="status">
          {notice}
        </div>
      )}
      <div className="integration-note">
        <h2>Подключение своей инфраструктуры</h2>
        <p>
          Стенд готов к подключению внешнего Prometheus. Адрес и токен задаются
          в настройках запуска, инструкция в README проекта. Аккаунт в облачном
          сервисе не требуется.
        </p>
      </div>
    </div>
  );
}

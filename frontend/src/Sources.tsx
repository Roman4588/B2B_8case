import { useState } from "react";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  FlaskConical,
  Radio,
  RefreshCw,
} from "lucide-react";
import { api, useResource } from "./api";
import type { Source } from "./types";
import { sourceStatusNames, time } from "./ui";

export function Sources() {
  const { data, error, refresh } = useResource<Source>("/sources");
  const readiness = useResource<{status: string; indexed_runbooks: number}>("/health/ready", 10000);
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
    <>
      <div className="section-heading">
        <div>
          <h2>Источники мониторинга</h2>
          <p>Состояние подключений и поступление событий</p>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="hint" role="status">
        API: {data ? "доступен" : "проверяется"}. База знаний: {readiness.data?.status === "ready"
          ? `готова, инструкций: ${readiness.data.indexed_runbooks}`
          : "подготовка или нет связи — дождитесь загрузки модели"}.
        Мониторинг проверяется отдельно ниже.
      </div>
      <section className="source-card">
        <header>
          <span className="prometheus-logo">
            <Radio size={27} />
          </span>
          <div>
            <h3>Prometheus</h3>
            <p>События через официальный HTTP API</p>
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
          <span>
            <CheckCircle2 size={15} />
            Повторные события объединяются автоматически
          </span>
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
          <span className="eyebrow">
            <FlaskConical size={15} /> ДЕМОНСТРАЦИОННЫЙ СТЕНД
          </span>
          <h3>Покажите весь путь от сигнала до решения</h3>
          <p>
            Выберите состояние учебной инфраструктуры. Настоящий Prometheus
            обнаружит изменение метрик и передаст события ассистенту.
          </p>
          <div className="scenario-buttons">
            <button
              className="secondary"
              onClick={() => void scenario("outage")}
            >
              <Activity size={16} />
              Аварийные события
              <ArrowUpRight size={14} />
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
        <h3>Подключение своей инфраструктуры</h3>
        <p>
          Стенд готов к подключению внешнего Prometheus. Адрес и токен задаются
          в настройках запуска — инструкция в README проекта. Аккаунт в облачном
          сервисе не требуется.
        </p>
      </div>
    </>
  );
}

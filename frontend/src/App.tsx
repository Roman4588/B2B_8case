import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  BellRing,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Command,
  LogOut,
  Radio,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api, useResource } from "./api";
import { Incidents } from "./Incidents";
import { Knowledge } from "./Knowledge";
import { Sources } from "./Sources";
import { Audit } from "./Audit";
import { sourceStatusNames } from "./ui";
import type { Source, Summary } from "./types";
import { time } from "./ui";

type Operator = { name: string; id: string };
const pages = [
  { id: "incidents", title: "События", icon: Activity },
  { id: "knowledge", title: "База знаний", icon: BookOpen },
  { id: "sources", title: "Источники", icon: Radio },
  { id: "audit", title: "Журнал действий", icon: ClipboardList },
];

export default function App() {
  const [operator, setOperator] = useState<Operator | null>(null);
  const [checking, setChecking] = useState(true);
  useEffect(() => {
    const expired = () => setOperator(null);
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    void api<Operator>("/auth/me")
      .then(setOperator)
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);
  if (checking)
    return (
      <div className="splash">
        <Sparkles /> Загружаем рабочее пространство…
      </div>
    );
  if (!operator) return <Login onLogin={setOperator} />;
  return (
    <Workspace
      operator={operator}
      onLogout={() => {
        void api("/auth/logout", { method: "POST" }).finally(() =>
          setOperator(null),
        );
      }}
    />
  );
}

function Login({ onLogin }: { onLogin: (operator: Operator) => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit() {
    setBusy(true);
    setError("");
    try {
      onLogin(
        await api<Operator>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ password }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand">
          <span className="brand-icon">
            <Command size={25} />
          </span>
          <strong>
            Сигналис<span>AI OPERATIONS COPILOT</span>
          </strong>
        </div>
        <div>
          <span className="eyebrow">СПОКОЙНАЯ СМЕНА НАЧИНАЕТСЯ ЗДЕСЬ</span>
          <h1>
            Меньше шума.
            <br />
            Больше ясности.
          </h1>
          <p>
            События мониторинга, опыт команды и понятный следующий шаг — в одном
            рабочем пространстве.
          </p>
          <div className="login-points">
            <span>
              <Check size={17} /> Разбор инцидентов
            </span>
            <span>
              <Check size={17} /> Проверенные регламенты
            </span>
            <span>
              <Check size={17} /> Решение всегда за вами
            </span>
          </div>
        </div>
      </section>
      <section className="login-form">
        <span className="sparkle-circle">
          <Sparkles size={27} />
        </span>
        <h2>Добро пожаловать на смену</h2>
        <p>Войдите в рабочее пространство инженера</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <label>
            Пароль
            <input
              type="password"
              required
              autoComplete="current-password"
              autoFocus
              placeholder="Введите пароль"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Входим…" : "Начать работу"}
            <ArrowRight size={17} />
          </button>
        </form>
      </section>
    </main>
  );
}

function Workspace({
  operator,
  onLogout,
}: {
  operator: Operator;
  onLogout: () => void;
}) {
  const [page, setPage] = useState("incidents");
  const [help, setHelp] = useState(false);
  const summary = useResource<Summary>("/summary");
  const source = useResource<Source>("/sources");
  const online = !source.error && source.data?.status === "online";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("incidents");
          }}
        >
          <span className="brand-icon">
            <Command size={23} />
          </span>
          <strong>
            Сигналис<span>AI OPERATIONS COPILOT</span>
          </strong>
        </a>
        <div className="workspace-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav>
          {pages.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => setPage(item.id)}
            >
              <item.icon size={19} />
              <span>{item.title}</span>
              {item.id === "incidents" && !!summary.data?.pending && (
                <b>{summary.data.pending}</b>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <Sparkles size={21} />
          <h3>Ассистент рядом</h3>
          <p>Поможет разобраться в событии и найти нужную инструкцию.</p>
          <span>
            <ShieldCheck size={13} /> Без автономных действий
          </span>
        </div>
        <div className="sidebar-bottom">
          <button onClick={() => setHelp(!help)}>
            <CircleHelp size={18} />
            Как это работает
          </button>
          <div>
            <span className="avatar">ДИ</span>
            <span>
              <strong>{operator.name}</strong>
              <small>Локальное пространство</small>
            </span>
            <button
              className="icon-button"
              aria-label="Выйти"
              onClick={onLogout}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>
            Рабочее пространство <ChevronRight size={13} />
            <strong>{pages.find((p) => p.id === page)?.title}</strong>
          </span>
          <div>
            <span className={"connection " + (online ? "online" : "offline")}>
              <i />
              {source.error
                ? "Нет связи с приложением"
                : sourceStatusNames[source.data?.status || "waiting"]}
            </span>
            <span className="today">
              {new Date().toLocaleDateString("ru-RU", {
                day: "numeric",
                month: "long",
              })}
            </span>
            <button
              className="icon-button mobile-logout"
              aria-label="Выйти из системы"
              onClick={onLogout}
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>
        <main className="main-content">
          <div className="page-intro">
            <div>
              <span className="eyebrow">AI OPERATIONS COPILOT / 08</span>
              <h1>
                {page === "incidents"
                  ? "Держите ситуацию под контролем."
                  : pages.find((p) => p.id === page)?.title}
              </h1>
              <p>
                {page === "incidents"
                  ? "Сигналы становятся понятными. Решения остаются за вами."
                  : "Ваше рабочее пространство для спокойной и предсказуемой смены."}
              </p>
            </div>
            <span className="shift-label">
              <span />
              Вы на смене
            </span>
          </div>
          {help && (
            <div className="help-banner">
              <strong>Как устроена работа</strong>
              <p>
                Откройте событие → прочитайте классификацию и регламент →
                примите решение → выполните действие самостоятельно → отметьте
                результат. В «Источниках» можно переключить учебный сценарий.
              </p>
              <button className="text-button" onClick={() => setHelp(false)}>
                Понятно
              </button>
            </div>
          )}
          {page === "incidents" && (
            <>
              <div className="stats-grid">
                <Stat
                  title="Критические"
                  value={summary.data?.critical}
                  tone="red"
                  icon={<BellRing size={19} />}
                  description="Требуют немедленного внимания"
                />
                <Stat
                  title="Предупреждения"
                  value={summary.data?.warning}
                  tone="amber"
                  icon={<Activity size={19} />}
                  description="Стоит проверить заранее"
                />
                <Stat
                  title="Информационные"
                  value={summary.data?.info}
                  tone="blue"
                  icon={<Radio size={19} />}
                  description="Плановые события и проверки"
                />
                <Stat
                  title="Инструкций в базе"
                  value={summary.data?.runbooks}
                  tone="mint"
                  icon={<BookOpen size={19} />}
                  description="Опыт команды под рукой"
                />
              </div>
              <Incidents onChanged={summary.refresh} />
            </>
          )}
          {page === "knowledge" && <Knowledge />}
          {page === "sources" && <Sources />}
          {page === "audit" && <Audit />}
          <footer className="page-footer">
            <span>
              <ShieldCheck size={14} /> Только рекомендации. Все действия
              выполняет инженер.
            </span>
            <span>
              Последняя синхронизация: {time(source.data?.state?.last_success)}
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function Stat({
  title,
  value,
  tone,
  icon,
  description,
}: {
  title: string;
  value?: number;
  tone: string;
  icon: React.ReactNode;
  description: string;
}) {
  return (
    <article className={"stat " + tone}>
      <div>
        <span>{title}</span>
        <i>{icon}</i>
      </div>
      <strong>{value ?? "—"}</strong>
      <p>{description}</p>
    </article>
  );
}

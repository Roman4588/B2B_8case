import { useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  LogOut,
  Radio,
  ShieldCheck,
  Users,
  UserRound,
} from "lucide-react";
import { api, useResource } from "./api";
import { Incidents } from "./Incidents";
import { Knowledge } from "./Knowledge";
import { Sources } from "./Sources";
import { Audit } from "./Audit";
import { sourceStatusNames } from "./ui";
import type { Source, Summary } from "./types";
import { time } from "./ui";

import {
  Brand,
  Login,
  PasswordChange,
  Employees,
  type Operator,
} from "./Accounts";
const pages = [
  { id: "incidents", title: "События", icon: Activity },
  { id: "knowledge", title: "База знаний", icon: BookOpen },
  { id: "sources", title: "Источники", icon: Radio },
  { id: "audit", title: "Журнал действий", icon: ClipboardList },
  { id: "users", title: "Сотрудники", icon: Users },
  { id: "profile", title: "Мой профиль", icon: UserRound },
];
const pageDescriptions: Record<string, string> = {
  incidents: "Состояние инфраструктуры и решения инженеров",
  knowledge: "Регламенты команды и поиск инструкций по событию",
  sources: "Подключение Prometheus и состояние синхронизации",
  audit: "Решения инженеров и изменения рабочего пространства",
  users: "Учётные записи и права доступа команды",
  profile: "Личные данные и безопасность учётной записи",
};

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
      <div className="splash signalis-auth" role="status">
        <Activity /> Загружаем рабочее пространство…
      </div>
    );
  if (!operator) return <Login onLogin={setOperator} />;
  const logout = () => {
    void api("/auth/logout", { method: "POST" }).finally(() =>
      setOperator(null),
    );
  };
  if (operator.must_change_password)
    return (
      <main className="password-gate signalis-auth">
        <PasswordChange
          operator={operator}
          onChanged={setOperator}
          onLogout={logout}
        />
      </main>
    );
  return (
    <Workspace
      operator={operator}
      onProfile={setOperator}
      onLogout={() => {
        void api("/auth/logout", { method: "POST" }).finally(() =>
          setOperator(null),
        );
      }}
    />
  );
}

function Workspace({
  operator,
  onLogout,
  onProfile,
}: {
  operator: Operator;
  onProfile: (operator: Operator) => void;
  onLogout: () => void;
}) {
  const [page, setPage] = useState("incidents");
  const [help, setHelp] = useState(false);
  const summary = useResource<Summary>("/summary");
  const source = useResource<Source>("/sources");
  const online = !source.error && source.data?.status === "online";
  return (
    <div className="app-shell events-screen" data-page={page}>
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("incidents");
          }}
        >
          <Brand />
        </a>
        <div className="workspace-label">Мониторинг инфраструктуры</div>
        <nav>
          {pages
            .filter((item) => item.id !== "users" || operator.role === "admin")
            .map((item) => (
              <button
                key={item.id}
                aria-current={page === item.id ? "page" : undefined}
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
        <div className="sidebar-bottom">
          <button onClick={() => setHelp(!help)}>
            <CircleHelp size={18} />
            Как это работает
          </button>
          <div>
            <span className="avatar">
              {operator.name
                .split(" ")
                .map((part) => part[0])
                .slice(0, 2)
                .join("")}
            </span>
            <span>
              <strong>{operator.name}</strong>
              <small>
                {operator.role === "admin" ? "Администратор" : "Инженер"}
              </small>
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
              <Radio size={14} aria-hidden="true" />
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
              <h1>
                {page === "incidents"
                  ? "События"
                  : pages.find((p) => p.id === page)?.title}
              </h1>
              <p>{pageDescriptions[page]}</p>
            </div>
            <span className="shift-label">
              <ShieldCheck size={15} aria-hidden="true" />
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
                  description="Требуют немедленного внимания"
                />
                <Stat
                  title="Предупреждения"
                  value={summary.data?.warning}
                  tone="amber"
                  description="Стоит проверить заранее"
                />
                <Stat
                  title="Информационные"
                  value={summary.data?.info}
                  tone="blue"
                  description="Плановые события и проверки"
                />
                <Stat
                  title="Инструкций в базе"
                  value={summary.data?.runbooks}
                  tone="mint"
                  description="Опыт команды под рукой"
                />
              </div>
              <Incidents onChanged={summary.refresh} />
            </>
          )}
          {page === "knowledge" && (
            <Knowledge canDelete={operator.role === "admin"} />
          )}
          {page === "sources" && <Sources />}
          {page === "audit" && <Audit />}
          {page === "users" && operator.role === "admin" && (
            <Employees operator={operator} />
          )}
          {page === "profile" && (
            <PasswordChange operator={operator} onChanged={onProfile} />
          )}
          {page === "incidents" && (
            <footer className="page-footer">
              <span>
                <ShieldCheck size={14} /> Только рекомендации. Все действия
                выполняет инженер.
              </span>
              <span>
                Последняя синхронизация:{" "}
                {time(source.data?.state?.last_success)}
              </span>
            </footer>
          )}
        </main>
      </div>
    </div>
  );
}

function Stat({
  title,
  value,
  tone,
  description,
}: {
  title: string;
  value?: number;
  tone: string;
  description: string;
}) {
  return (
    <article className={"stat " + tone}>
      <div>
        <span>{title}</span>
      </div>
      <strong>{value ?? "—"}</strong>
      <p>{description}</p>
    </article>
  );
}

import { useState } from "react";
import { Eye, EyeOff, Plus } from "lucide-react";
import { api, useResource } from "./api";

export type Operator = {
  id: string;
  name: string;
  email: string;
  role: "admin" | "engineer";
  is_active: boolean;
  must_change_password: boolean;
};

export function PasswordField({
  label,
  value,
  onChange,
  fresh = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  fresh?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <label>
      {label}
      <span className="password-input">
        <input
          type={visible ? "text" : "password"}
          required
          value={value}
          minLength={fresh ? 12 : undefined}
          maxLength={128}
          autoComplete={fresh ? "new-password" : "current-password"}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          className="icon-button"
          aria-label={`${visible ? "Скрыть" : "Показать"}: ${label}`}
          aria-pressed={visible}
          onClick={() => setVisible(!visible)}
        >
          {visible ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </span>
    </label>
  );
}

export function Brand() {
  return (
    <>
      <span className="brand-icon">
        <span>
          B<span>2</span>B
        </span>
      </span>
      <strong className="brand-name">
        Сигналис<span className="brand-name">B2B-CENTER</span>
      </strong>
    </>
  );
}

export function Login({ onLogin }: { onLogin: (operator: Operator) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(
        await api<Operator>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page corporate-login signalis-auth">
      <section className="login-story">
        <div className="brand">
          <Brand />
        </div>
        <div className="login-message">
          <h1>Мониторинг инфраструктуры</h1>
          <p>
            События инфраструктуры, решения дежурного инженера и база знаний
            команды в одном рабочем пространстве.
          </p>
        </div>
        <span className="login-signature">Рабочее пространство команды</span>
      </section>
      <section className="login-form">
        <h2>Добро пожаловать</h2>
        <p>Войдите с учётной записью сотрудника</p>
        <form onSubmit={submit}>
          <label>
            Рабочий email
            <input
              type="email"
              required
              autoComplete="username"
              autoFocus
              placeholder="name@company.ru"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <PasswordField
            label="Пароль"
            value={password}
            onChange={setPassword}
          />
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Входим…" : "Войти"}
          </button>
        </form>
        <p className="access-note">
          Нет доступа или забыли пароль?
          <br />
          Обратитесь к администратору вашей команды.
        </p>
      </section>
    </main>
  );
}

export function PasswordChange({
  operator,
  onChanged,
  onLogout,
}: {
  operator: Operator;
  onChanged: (operator: Operator) => void;
  onLogout?: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);
    if (password !== repeat) {
      setError("Пароли не совпадают");
      return;
    }
    setBusy(true);
    try {
      const updated = await api<Operator>("/auth/password", {
        method: "POST",
        body: JSON.stringify({
          current_password: current,
          new_password: password,
        }),
      });
      setCurrent("");
      setPassword("");
      setRepeat("");
      setSuccess(true);
      onChanged(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="account-panel password-panel">
      <h2>
        {operator.must_change_password
          ? "Задайте личный пароль"
          : "Смена пароля"}
      </h2>
      <p>
        <span>{operator.name}</span>
        <span>{operator.email}</span>
      </p>
      {operator.must_change_password && (
        <p className="hint">
          Вы вошли с временным паролем. Замените его, чтобы открыть рабочее
          пространство.
        </p>
      )}
      <form onSubmit={submit} className="account-form">
        <PasswordField
          label="Текущий пароль"
          value={current}
          onChange={setCurrent}
        />
        <PasswordField
          label="Новый пароль"
          value={password}
          onChange={setPassword}
          fresh
        />
        <PasswordField
          label="Повторите новый пароль"
          value={repeat}
          onChange={setRepeat}
          fresh
        />
        <p className="subtle">
          От 12 до 128 символов, включая буквы и цифры. После смены другие
          сессии будут завершены.
        </p>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {success && (
          <div className="hint" role="status">
            Пароль изменён.
          </div>
        )}
        <button className="primary" disabled={busy}>
          {busy ? "Сохраняем…" : "Сохранить пароль"}
        </button>
        {onLogout && (
          <button type="button" className="text-button" onClick={onLogout}>
            Выйти
          </button>
        )}
      </form>
    </section>
  );
}

export function Employees({ operator }: { operator: Operator }) {
  const resource = useResource<Operator[]>("/users");
  const [editing, setEditing] = useState<Operator | "new" | null>(null);
  const [statusTarget, setStatusTarget] = useState<Operator | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function toggle() {
    if (!statusTarget) return;
    setBusy(true);
    setError("");
    try {
      await api(`/users/${statusTarget.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !statusTarget.is_active }),
      });
      resource.refresh();
      setStatusTarget(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="employees">
      <div className="employee-toolbar">
        <div>
          <h2>Доступ команды</h2>
          <p>Персональные аккаунты и права сотрудников</p>
        </div>
        <button className="primary" onClick={() => setEditing("new")}>
          <Plus size={18} />
          Добавить сотрудника
        </button>
      </div>
      {(error || resource.error) && (
        <div className="error" role="alert">
          {error || resource.error}
        </div>
      )}
      {!resource.data && !resource.error && (
        <p className="loading">Загружаем сотрудников…</p>
      )}
      <div className="employee-list">
        {resource.data?.map((user) => (
          <article className="employee-card" key={user.id}>
            <div className="employee-info">
              <h3>
                {user.name}
                {user.id === operator.id && <small>Вы</small>}
              </h3>
              <p>{user.email}</p>
              <div className="employee-meta">
                <span>
                  {user.role === "admin" ? "Администратор" : "Инженер"}
                </span>
                <span>
                  {user.is_active ? "Доступ открыт" : "Доступ отключён"}
                </span>
              </div>
              {user.must_change_password && user.is_active && (
                <small>Ожидается смена временного пароля</small>
              )}
            </div>
            {user.id !== operator.id && (
              <div className="employee-actions">
                <button className="secondary" onClick={() => setEditing(user)}>
                  Сбросить пароль
                </button>
                <button
                  className="text-button"
                  onClick={() => {
                    setError("");
                    setStatusTarget(user);
                  }}
                >
                  {user.is_active ? "Отключить доступ" : "Включить доступ"}
                </button>
              </div>
            )}
          </article>
        ))}
      </div>
      {statusTarget && (
        <div
          className="confirm-access"
          role="dialog"
          aria-modal="true"
          aria-label="Изменить доступ"
        >
          <div className="account-panel">
            <h2>
              {statusTarget.is_active
                ? "Отключить доступ?"
                : "Включить доступ?"}
            </h2>
            <p>
              <span>{statusTarget.name}</span>
              <span>{statusTarget.email}</span>
            </p>
            <p>
              {statusTarget.is_active
                ? "Все сессии сотрудника будут завершены. История его решений сохранится."
                : "Сотрудник сможет снова войти со своим паролем."}
            </p>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <div className="dialog-actions">
              <button
                className="secondary"
                disabled={busy}
                onClick={() => setStatusTarget(null)}
              >
                Отмена
              </button>
              <button
                className="primary"
                disabled={busy}
                onClick={() => void toggle()}
              >
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      )}
      {editing && (
        <UserEditor
          key={typeof editing === "string" ? editing : editing.id}
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            resource.refresh();
            setEditing(null);
          }}
        />
      )}
    </section>
  );
}

function UserEditor({
  user,
  onClose,
  onSaved,
}: {
  user: Operator | "new";
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("engineer");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(user === "new" ? "/users" : `/users/${user.id}/password`, {
        method: "POST",
        body: JSON.stringify(
          user === "new" ? { name, email, role, password } : { password },
        ),
      });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div
      className="confirm-access"
      role="dialog"
      aria-modal="true"
      aria-label={user === "new" ? "Добавить сотрудника" : "Сбросить пароль"}
    >
      <section className="account-panel">
        <h2>{user === "new" ? "Новый сотрудник" : "Сброс пароля"}</h2>
        {user !== "new" && (
          <p>
            <span>{user.name}</span>
            <span>{user.email}</span>
          </p>
        )}
        <form className="account-form" onSubmit={submit}>
          {user === "new" && (
            <>
              <label>
                Имя сотрудника
                <input
                  required
                  maxLength={120}
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label>
                Email сотрудника
                <input
                  type="email"
                  required
                  maxLength={254}
                  autoComplete="off"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <label>
                Роль
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="engineer">Инженер</option>
                  <option value="admin">Администратор</option>
                </select>
              </label>
            </>
          )}
          <PasswordField
            label="Временный пароль"
            value={password}
            onChange={setPassword}
            fresh
          />
          <p className="subtle">
            Минимум 12 символов, буквы и цифры. Передайте пароль сотруднику по
            защищённому каналу. При входе он задаст собственный пароль.
          </p>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={onClose}
            >
              Отмена
            </button>
            <button className="primary" disabled={busy}>
              {busy ? "Сохраняем…" : "Сохранить"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

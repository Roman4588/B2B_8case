import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Database,
  Globe2,
  Info,
  Layers3,
  Server,
  ShieldCheck,
} from "lucide-react";
import type { Category, Severity } from "./types";

export const categoryNames: Record<Category, string> = {
  server: "Сервер",
  network: "Сеть",
  database: "База данных",
  application: "Приложение",
};
export const categoryIcons = {
  server: Server,
  network: Globe2,
  database: Database,
  application: Layers3,
};
export const severityNames: Record<Severity, string> = {
  critical: "Критическое",
  warning: "Предупреждение",
  info: "Информация",
};
export const handlingNames: Record<string, string> = {
  new: "Ожидает решения",
  accepted: "Принято инженером",
  completed: "Выполнено вручную",
  dismissed: "Отклонено",
};
export const actionNames: Record<string, string> = {
  user_created: "Создан сотрудник",
  user_enabled: "Доступ включён",
  user_disabled: "Доступ отключён",
  password_changed: "Изменён личный пароль",
  password_reset: "Сброшен пароль",
  account_provisioned: "Настройка учётной записи",
  accept: "Принято к ручному выполнению",
  complete: "Выполнено вручную",
  dismiss: "Рекомендация отклонена",
  runbook_create: "Добавлена инструкция",
  runbook_update: "Обновлена инструкция",
  document_upload: "Загружен документ",
  demo_scenario: "Изменён учебный сценарий",
};
export const jobNames: Record<string, string> = {
  queued: "В очереди",
  running: "Обработка",
  succeeded: "Готово",
  failed: "Ошибка",
  ready: "Готово",
};
export const sourceStatusNames = {
  waiting: "Ожидаем синхронизацию",
  online: "Мониторинг подключён",
  stale: "Данные мониторинга устарели",
  error: "Ошибка подключения",
};
export function time(value?: string | null) {
  return value
    ? new Date(value).toLocaleString("ru-RU", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Ещё не было";
}
export function SeverityBadge({ value }: { value: Severity }) {
  const Icon =
    value === "critical" ? AlertCircle : value === "warning" ? Clock3 : Info;
  return (
    <span className={"badge " + value}>
      <Icon size={13} />
      {severityNames[value]}
    </span>
  );
}
export function Empty({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="empty">
      <CheckCircle2 size={32} />
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
export function SafetyNote() {
  return (
    <div className="safety-note">
      <ShieldCheck size={17} />
      <span>
        Решение за инженером. Ассистент рекомендует действия, вы выполняете их
        вручную.
      </span>
    </div>
  );
}

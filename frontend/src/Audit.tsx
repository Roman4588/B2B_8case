import { ClipboardCheck } from "lucide-react";
import { useResource } from "./api";
import type { Audit as AuditEntry } from "./types";
import { actionNames, Empty, time } from "./ui";
export function Audit() {
  const { data, error } = useResource<AuditEntry[]>("/audit");
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Журнал действий</h2>
          <p>Кто принял решение и что было выполнено вручную</p>
        </div>
        <span className="subtle">Последние 100 записей</span>
      </div>
      {error && <div className="error">{error}</div>}
      {data?.length === 0 && (
        <Empty
          title="Решений пока нет"
          description="Принятые решения и изменения базы знаний появятся здесь."
        />
      )}
      <div className="audit-list">
        {data?.map((row) => (
          <article key={row.id}>
            <span className="audit-icon">
              <ClipboardCheck size={19} />
            </span>
            <div>
              <h3>{actionNames[row.action] || row.action}</h3>
              <p>
                {row.actor}
                <span> · {time(row.created_at)}</span>
              </p>
              {row.comment && <blockquote>{row.comment}</blockquote>}
              {row.incident_id && (
                <small>Событие · {row.incident_id.slice(0, 8)}</small>
              )}
            </div>
            <span className="audit-mark">Записано</span>
          </article>
        ))}
      </div>
    </>
  );
}

import { useState } from "react";
import { useResource } from "./api";
import { ShowMore } from "./ShowMore";
import type { Audit as AuditEntry } from "./types";
import { actionNames, Empty, time } from "./ui";
export function Audit() {
  const [visible, setVisible] = useState(10);
  const { data, error } = useResource<AuditEntry[]>("/audit");
  return (
    <>
      <div className="section-heading audit-summary">
        <div>
          <p>Кто принял решение и что было выполнено вручную</p>
        </div>
        <span className="subtle">Записей: {data?.length ?? "—"}</span>
      </div>
      {error && <div className="error">{error}</div>}
      {data?.length === 0 && (
        <Empty
          title="Решений пока нет"
          description="Принятые решения и изменения базы знаний появятся здесь."
        />
      )}
      <div className="audit-list" id="audit-record-list">
        {data?.slice(0, visible).map((row) => (
          <article key={row.id}>
            <div className="audit-record">
              <h3>{actionNames[row.action] || row.action}</h3>
              <div className="audit-metadata">
                <span className="audit-actor">{row.actor}</span>
                <time dateTime={row.created_at}>{time(row.created_at)}</time>
              </div>
              {row.comment && <blockquote>{row.comment}</blockquote>}
              {row.incident_id && (
                <small>Событие: {row.incident_id.slice(0, 8)}</small>
              )}
            </div>
          </article>
        ))}
      </div>
      <ShowMore
        shown={visible}
        total={data?.length ?? 0}
        onMore={() => setVisible((n) => n + 10)}
        label="Показать ещё записи"
        controls="audit-record-list"
      />
    </>
  );
}

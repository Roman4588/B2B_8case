// Local design review only. This server never connects to the production API.
import { createServer } from "vite";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const books = JSON.parse(
  readFileSync(
    new URL("../../backend/app/seed/runbooks.json", import.meta.url),
  ),
);
const cases = [
  [
    "PostgreSQL: основной узел недоступен",
    "db-01",
    "critical",
    "database",
    "P1",
    "new",
    "Отказ PostgreSQL",
  ],
  [
    "Nginx: ошибки 502/503",
    "app-02",
    "critical",
    "application",
    "P1",
    "accepted",
    "Nginx: ошибки 502/503",
  ],
  [
    "Заканчивается место на диске сервера",
    "storage-01",
    "warning",
    "server",
    "P3",
    "new",
    "",
  ],
  [
    "Отставание репликации БД",
    "db-replica-01",
    "warning",
    "database",
    "P2",
    "accepted",
    "Отставание репликации БД",
  ],
  [
    "Потери пакетов в сети",
    "gateway-01",
    "warning",
    "network",
    "P3",
    "new",
    "Потери пакетов в сети",
  ],
  [
    "Проверка резервной копии завершена",
    "backup-01",
    "info",
    "server",
    "P4",
    "completed",
    "",
  ],
];
const fixedTime = new Date("2026-10-30T09:42:00Z");
const items = cases.map(
  ([title, host, severity, category, priority, handling, bookTitle], i) => {
    const book = books.find((b) => b.title === bookTitle);
    return {
      id: `preview-${i + 1}`,
      title,
      host,
      severity,
      category,
      priority,
      handling,
      source: "Prometheus",
      lifecycle: "firing",
      confidence: 0.9,
      needs_review: true,
      description: book?.condition || title,
      rationale:
        "Классификация по признакам события и меткам источника. Проверьте доступность узла и подтвердите причину отказа.",
      first_seen: new Date(+fixedTime - i * 7 * 60000).toISOString(),
      last_seen: fixedTime.toISOString(),
      labels: {},
      recommendation_status: "ready",
      recommendations: book
        ? [
            {
              ...book,
              id: `book-${i}`,
              source: "База знаний команды",
              similarity: 0.91,
              revision: 1,
              excerpt: "",
            },
          ]
        : [],
    };
  },
);
const history = new Map(items.map((i) => [i.id, []]));
const previewUsers = [
  {
    id: "preview",
    name: "Демо-инженер",
    email: "preview@example.org",
    role: "admin",
    is_active: true,
    must_change_password: false,
  },
  {
    id: "engineer-2",
    name: "Инженер поддержки",
    email: "support@example.org",
    role: "engineer",
    is_active: true,
    must_change_password: false,
  },
  {
    id: "engineer-3",
    name: "Новый сотрудник",
    email: "new@example.org",
    role: "engineer",
    is_active: true,
    must_change_password: true,
  },
];
const previewAudit = [
  {
    id: "audit-1",
    actor: "Демо-инженер",
    action: "accept",
    comment: "Проверяю доступность основного узла и состояние реплики.",
    created_at: fixedTime.toISOString(),
    incident_id: "preview-1",
  },
  {
    id: "audit-2",
    actor: "Инженер поддержки",
    action: "runbook_update",
    comment: "Уточнён порядок проверки сетевого подключения.",
    created_at: new Date(+fixedTime - 12 * 60000).toISOString(),
    incident_id: null,
  },
  {
    id: "audit-3",
    actor: "Демо-инженер",
    action: "complete",
    comment: "Состояние службы проверено вручную.",
    created_at: new Date(+fixedTime - 28 * 60000).toISOString(),
    incident_id: "preview-2",
  },
];
let signedIn = true;
const server = await createServer({
  configFile: fileURLToPath(new URL("../vite.config.ts", import.meta.url)),
  root: fileURLToPath(new URL("../", import.meta.url)),
  server: {
    host: "127.0.0.1",
    port: Number(process.env.PREVIEW_PORT || 5173),
    strictPort: true,
  },
  plugins: [
    {
      name: "local-design-preview",
      transformIndexHtml(html, context) {
        const screen = new URL(
          context.originalUrl || "/",
          "http://127.0.0.1",
        ).searchParams.get("previewScreen");
        const label = {
          knowledge: "База знаний",
          sources: "Источники",
          audit: "Журнал действий",
          employees: "Сотрудники",
          profile: "Мой профиль",
        }[screen];
        const navigation = label
          ? `<script type="module">const observer=new MutationObserver(()=>{const button=[...document.querySelectorAll('nav button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(button){observer.disconnect();button.click();}});observer.observe(document.body,{childList:true,subtree:true});</script>`
          : "";
        return html
          .replace("</body>", navigation + "</body>")
          .replace(
            "<body>",
            '<body><style>#design-preview-note{padding:6px 16px;margin-left:212px;border-bottom:1px solid #62531e;background:#fff4c9;color:#4d4117;font:12px system-ui}@media(max-width:700px){#design-preview-note{margin-left:0}}</style><div id="design-preview-note">Предпросмотр дизайна: тестовые данные, без подключения к серверу</div>',
          );
      },
      configureServer(vite) {
        vite.middlewares.use(async (req, res, next) => {
          const url = new URL(req.url, "http://127.0.0.1");
          if (!url.pathname.startsWith("/api/")) return next();
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.setHeader("Cache-Control", "no-store");
          const send = (body, status = 200) => {
            res.statusCode = status;
            res.end(JSON.stringify(body));
          };
          const path = url.pathname.slice(4);
          const previewScreen = new URL(
            req.headers.referer || "/",
            "http://127.0.0.1",
          ).searchParams.get("previewScreen");
          if (path === "/auth/me" && previewScreen === "login")
            return send({ detail: "Войдите в систему" }, 401);
          if (path === "/auth/logout") {
            signedIn = false;
            return send({});
          }
          if (path === "/auth/login") signedIn = true;
          if (!signedIn) return send({ detail: "Войдите в систему" }, 401);
          if (["/auth/me", "/auth/login"].includes(path))
            return send({
              id: "preview",
              name: "Демо-инженер",
              email: "preview@example.org",
              role: "admin",
              is_active: true,
              must_change_password: false,
            });
          if (path === "/health/ready")
            return send({ status: "ready", indexed_runbooks: books.length });
          if (path === "/summary")
            return send({
              critical: 2,
              warning: 3,
              info: 1,
              pending: items.filter((i) => i.handling === "new").length,
              runbooks: books.length,
            });
          if (path === "/sources")
            return send({
              source: "Prometheus",
              status: "online",
              interval_seconds: 15,
              stale_after_seconds: 60,
              demo_mode: true,
              state: {
                last_success: fixedTime.toISOString(),
                last_attempt: fixedTime.toISOString(),
                count: items.length,
                error: "",
              },
            });
          if (path === "/incidents") {
            const matches = items.filter((item) => {
              const q = (url.searchParams.get("q") || "").toLowerCase();
              if (!(item.title + item.host).toLowerCase().includes(q))
                return false;
              return (
                ["severity", "category", "priority", "handling"].every(
                  (key) =>
                    !url.searchParams.get(key) ||
                    item[key] === url.searchParams.get(key),
                ) &&
                (!url.searchParams.get("state") ||
                  item.lifecycle === url.searchParams.get("state"))
              );
            });
            return send({ items: matches, total: matches.length });
          }
          const match = path.match(
            /^\/incidents\/([^/]+)(?:\/(history|actions|recommendations\/retry))?$/,
          );
          if (match) {
            const item = items.find((i) => i.id === match[1]);
            if (!item) return send({ detail: "Событие не найдено" }, 404);
            if (match[2] === "history") return send(history.get(item.id));
            if (match[2] === "actions") {
              let raw = "";
              for await (const chunk of req) raw += chunk;
              const body = JSON.parse(raw || "{}");
              const handling = {
                accept: "accepted",
                complete: "completed",
                dismiss: "dismissed",
              }[body.action];
              if (!handling)
                return send({ detail: "Неизвестное действие" }, 422);
              item.handling = handling;
              history.get(item.id).push({
                id: String(Date.now()),
                incident_id: item.id,
                actor: "Демо-инженер",
                action: body.action,
                comment: body.comment || "",
                created_at: new Date().toISOString(),
              });
            }
            return send(item);
          }
          if (path === "/audit")
            return send([...history.values()].flat().concat(previewAudit));
          if (path === "/runbooks")
            return send({
              items: books.map((b, i) => ({
                ...b,
                id: `book-${i}`,
                source: "База знаний команды",
                status: "ready",
              })),
              semantic: false,
            });
          if (path === "/users") return send(previewUsers);
          if (path === "/jobs") return send([]);
          return send(
            { detail: "Это действие недоступно в предпросмотре дизайна" },
            501,
          );
        });
      },
    },
  ],
});
await server.listen();
server.printUrls();

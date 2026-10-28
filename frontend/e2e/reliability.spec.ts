import { test, expect, type Page } from "@playwright/test";

test.use({ screenshot: { mode: "on", fullPage: true } });

// UI regressions use deterministic API responses. operator.spec.ts exercises
// the real Compose stack; these tests also run against the Vite preview.
async function mockWorkspace(
  page: Page,
  status = "pending",
  sourceStatus = "stale",
) {
  let recommendationStatus = status;
  const incident = {
    id: "event",
    title: "PostgreSQL: основной узел недоступен",
    description: "No connection",
    host: "db-01",
    severity: "critical",
    category: "database",
    priority: "P1",
    confidence: 0.9,
    needs_review: true,
    rationale: "Нужна проверка инженера",
    lifecycle: "firing",
    handling: "new",
    first_seen: new Date().toISOString(),
    last_seen: new Date().toISOString(),
    labels: {},
  };
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let body: unknown = {};
    if (url.pathname === "/api/auth/me")
      body = { id: "operator", name: "Инженер", email: "engineer@example.org", role: "engineer", is_active: true, must_change_password: false };
    else if (url.pathname === "/api/summary")
      body = { critical: 1, warning: 0, info: 0, pending: 1, runbooks: 1 };
    else if (url.pathname === "/api/sources")
      body = {
        source: "Prometheus",
        status: sourceStatus,
        interval_seconds: 15,
        stale_after_seconds: 60,
        demo_mode: false,
        state: {
          last_success: new Date(Date.now() - 120000).toISOString(),
          last_attempt: null,
          error: "",
          count: 1,
        },
      };
    else if (url.pathname === "/api/incidents")
      body = { items: [incident], total: 1, page: 1 };
    else if (url.pathname.endsWith("/recommendations/retry")) {
      recommendationStatus = "ready";
      body = { status: "queued" };
    } else if (url.pathname === "/api/incidents/event")
      body = {
        ...incident,
        recommendation_status: recommendationStatus,
        recommendations: [
          {
            id: "book",
            title:
              recommendationStatus === "ready"
                ? "Новый регламент"
                : "Устаревший совет",
            condition: "Database down",
            steps: ["Проверить подключение"],
            cautions: "Согласуйте действия",
            source: "Регламент",
            revision: 1,
            similarity: 0.8,
          },
        ],
      };
    else if (url.pathname === "/api/runbooks")
      body = { items: [], semantic: false };
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname === "/api/incidents/event/history")
      body = [
        {
          id: "decision",
          incident_id: "event",
          actor: "Инженер",
          action: "accept",
          comment: "Проверил первичный узел",
          created_at: new Date().toISOString(),
        },
      ];
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await expect(page.locator(".event-row")).toBeVisible();
}

test("pending recommendations never display advice from an older event", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.locator(".event-row").click();
  await expect(
    page.getByText("Ищем подходящие регламенты", { exact: false }),
  ).toBeVisible();
  await expect(page.locator(".recommendation")).toHaveCount(0);
  await expect(page.locator(".confidence")).toContainText(
    "Нужна ручная проверка",
  );
  await expect(page.locator(".confidence")).not.toContainText("90%");
});

test("incident card shows decisions for its episode", async ({ page }) => {
  await mockWorkspace(page, "ready");
  await page.locator(".event-row").click();
  await expect(
    page.getByRole("region", { name: "История решений" }),
  ).toContainText("Проверил первичный узел");
  await expect(
    page.getByRole("region", { name: "История решений" }),
  ).toContainText("Принято к ручному выполнению");
});

test("stalled polling stops showing a green connection and can recover", async ({
  page,
}) => {
  await page.clock.install();
  await mockWorkspace(page, "ready", "online");
  await expect(page.locator(".topbar .connection")).toHaveClass(/online/);
  await page.route("**/api/sources", () => new Promise(() => {}));
  const request = page.waitForRequest("**/api/sources");
  await page.clock.runFor(5000);
  await request;
  await page.clock.fastForward(31000);
  await expect(page.locator(".topbar .connection")).not.toHaveClass(/online/);
  await page.unroute("**/api/sources");
  await page.clock.runFor(5000);
  await expect(page.locator(".topbar .connection")).toHaveClass(/online/);
});

test("expired session returns the operator to login", async ({ page }) => {
  await page.clock.install();
  await mockWorkspace(page);
  await page.route("**/api/summary", (route) =>
    route.fulfill({ status: 401, json: { detail: "Войдите в систему" } }),
  );
  await page.clock.runFor(5000);
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible();
  await expect(page.locator(".app-shell")).toHaveCount(0);
});

test("failed recommendation search can be retried", async ({ page }) => {
  await mockWorkspace(page, "failed");
  await page.locator(".event-row").click();
  await page.getByRole("button", { name: "Повторить поиск" }).click();
  await expect(page.locator(".recommendation")).toContainText(
    "Новый регламент",
  );
});

test("stale monitoring is visible and workflow filters reach the API", async ({
  page,
}) => {
  await mockWorkspace(page);
  await expect(page.locator(".topbar .connection")).toContainText(
    "Данные мониторинга устарели",
  );
  const priorityRequest = page.waitForRequest(
    (r) =>
      r.url().includes("/api/incidents?") && r.url().includes("priority=P1"),
  );
  await page.getByLabel("Приоритет", { exact: true }).selectOption("P1");
  await priorityRequest;
  const handlingRequest = page.waitForRequest((r) =>
    r.url().includes("handling=accepted"),
  );
  await page.getByLabel("Статус обработки").selectOption("accepted");
  await handlingRequest;
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Источники" })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Показанные события могут быть устаревшими",
  );
});

test("readable mobile dashboard and filters do not overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockWorkspace(page);
  await expect(page.getByLabel("Приоритет", { exact: true })).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("dashboard.png"),
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.locator(".event-row").click();
  expect(
    await page
      .locator(".detail-panel")
      .evaluate((el) => el.scrollWidth <= el.clientWidth),
  ).toBe(true);
});

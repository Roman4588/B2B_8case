import { test, expect, type Page } from "@playwright/test";

async function openIncident(
  page: Page,
  description = "Нет соединения с основным узлом PostgreSQL.",
) {
  const incident = {
    id: "event",
    title: "PostgreSQL: основной узел недоступен",
    description,
    host: "db-primary",
    source: "Prometheus",
    severity: "critical",
    category: "database",
    priority: "P1",
    confidence: 0.9,
    needs_review: true,
    rationale:
      "Сервис недоступен по меткам источника. Причину должен подтвердить инженер.",
    lifecycle: "firing",
    handling: "new",
    first_seen: "2026-10-31T05:00:00Z",
    last_seen: "2026-10-31T05:00:00Z",
    labels: {},
    recommendation_status: "ready",
    recommendations: Array.from({ length: 3 }, (_, i) => ({
      id: `book-${i}`,
      title: `Проверка PostgreSQL ${i + 1}`,
      condition: "Отказ БД",
      category: "database",
      source: "Регламент команды",
      revision: 1,
      similarity: 0.9 - i / 10,
      excerpt: "",
      cautions: "Не повышайте реплику без согласования.",
      steps: [
        "Проверить доступность узла и порт 5432, выполнить pg_isready.",
        "Проверить состояние службы, журнал ошибок и свободное место.",
        "Согласовать восстановление с администратором базы данных.",
        "После ручного действия проверить чтение, запись и репликацию.",
      ],
    })),
  };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let json: unknown = {};
    if (path === "/api/auth/me")
      json = {
        id: "engineer",
        name: "Инженер",
        email: "engineer@example.org",
        role: "engineer",
        is_active: true,
        must_change_password: false,
      };
    else if (path === "/api/summary")
      json = { critical: 1, warning: 0, info: 0, pending: 1, runbooks: 3 };
    else if (path === "/api/sources")
      json = {
        status: "online",
        source: "Prometheus",
        state: { last_success: incident.last_seen, count: 1, error: "" },
        interval_seconds: 15,
      };
    else if (path === "/api/incidents") json = { items: [incident], total: 1 };
    else if (path === "/api/incidents/event") json = incident;
    else if (path === "/api/incidents/event/history")
      json = [
        {
          id: "audit",
          incident_id: "event",
          actor: "Инженер",
          action: "accept",
          comment: "Проверены метрики узла",
          created_at: incident.first_seen,
        },
      ];
    else if (path === "/api/incidents/event/actions") {
      const body = route.request().postDataJSON();
      incident.handling = body.action === "accept" ? "accepted" : "completed";
      json = incident;
    }
    await route.fulfill({ json });
  });
  await page.goto("/");
  await page.locator(".event-row").click();
  await expect(page.locator(".recommendation")).toHaveCount(3);
}

test("engineer decision stays reachable while reading long recommendations", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openIncident(page);
  const accept = page.getByRole("button", {
    name: "Принято к ручному выполнению",
    exact: true,
  });
  await expect(accept).toBeInViewport({ ratio: 1 });
  await expect(page.getByLabel("Комментарий", { exact: true })).toBeInViewport({
    ratio: 1,
  });
  await page
    .locator(".incident-reading")
    .evaluate((el) => el.scrollTo(0, el.scrollHeight));
  await expect(
    page.getByRole("region", { name: "История решений" }),
  ).toContainText("Проверены метрики узла");
  await expect(accept).toBeInViewport({ ratio: 1 });
  await page
    .getByLabel("Комментарий", { exact: true })
    .fill("Проверю доступность узла вручную");
  const request = page.waitForRequest(
    (r) => r.url().endsWith("/actions") && r.method() === "POST",
  );
  await accept.click();
  expect((await request).postDataJSON()).toEqual({
    action: "accept",
    comment: "Проверю доступность узла вручную",
  });
  await expect(page.locator(".current-state")).toHaveText("Принято инженером");
});

test("mobile decision fits and classification explanation remains available", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await openIncident(page);
  await expect(
    page.getByRole("button", {
      name: "Принято к ручному выполнению",
      exact: true,
    }),
  ).toBeInViewport({ ratio: 1 });
  expect(
    await page
      .locator(".detail-panel")
      .evaluate((el) => el.scrollWidth > el.clientWidth),
  ).toBe(false);
  await page.getByText("Обоснование классификации", { exact: true }).click();
  await expect(
    page.getByText(
      "Сервис недоступен по меткам источника. Причину должен подтвердить инженер.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Закрыть событие")).toBeInViewport({ ratio: 1 });
  await page.getByLabel("Закрыть событие").click();
  await expect(page.locator(".detail-content")).toHaveCount(0);
});

test("long source descriptions do not push the decision out of the panel", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openIncident(
    page,
    "Подробное описание источника и результаты проверки доступности узла. ".repeat(
      45,
    ),
  );
  await expect(
    page.getByRole("button", {
      name: "Принято к ручному выполнению",
      exact: true,
    }),
  ).toBeInViewport({ ratio: 1 });
});

test("short mobile viewport can scroll to the comment and decision", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 360 });
  await openIncident(page);
  const comment = page.getByLabel("Комментарий", { exact: true });
  await comment.scrollIntoViewIfNeeded();
  await expect(comment).toBeInViewport({ ratio: 1 });
  const accept = page.getByRole("button", {
    name: "Принято к ручному выполнению",
    exact: true,
  });
  await accept.scrollIntoViewIfNeeded();
  await expect(accept).toBeInViewport({ ratio: 1 });
});

test("compact laptop keeps a usable reading region after expanding the comment", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 768 });
  await openIncident(page);
  await page.getByLabel("Комментарий", { exact: true }).evaluate((el) => {
    el.style.height = "100px";
  });
  expect(
    await page.locator(".incident-reading").evaluate((el) => el.clientHeight),
  ).toBeGreaterThanOrEqual(120);
  const accept = page.getByRole("button", {
    name: "Принято к ручному выполнению",
    exact: true,
  });
  await accept.scrollIntoViewIfNeeded();
  await expect(accept).toBeInViewport({ ratio: 1 });
});

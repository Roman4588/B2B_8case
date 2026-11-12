import { test, expect } from "@playwright/test";

for (const newerVote of [false, true]) {
  test(`a delayed feedback response preserves newer incident data from polling (newer vote: ${newerVote})`, async ({
    page,
  }) => {
    const item: any = {
      id: "event",
      title: "Disk full",
      description: "Диск",
      host: "host",
      severity: "critical",
      category: "server",
      priority: "P1",
      confidence: 0.9,
      needs_review: false,
      rationale: "Автоматически",
      lifecycle: "firing",
      handling: "new",
      first_seen: new Date().toISOString(),
      last_seen: new Date().toISOString(),
      labels: {},
      recommendation_status: "ready",
      recommendation_generation: 5,
      recommendations: [
        {
          id: "book",
          title: "Инструкция",
          condition: "disk",
          steps: ["Check"],
          cautions: "",
          source: "Test",
          category: "server",
          similarity: 0.8,
          revision: 1,
          feedback: null,
        },
      ],
    };
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let body: any = {};
      if (path === "/api/auth/me")
        body = {
          id: "operator",
          name: "Engineer",
          email: "e@example.org",
          role: "engineer",
        };
      else if (path === "/api/sources")
        body = { status: "online", source: "Prometheus", state: null };
      else if (path === "/api/summary")
        body = { critical: 1, warning: 0, info: 0, pending: 1, runbooks: 1 };
      else if (path === "/api/incidents") body = { items: [item], total: 1 };
      else if (path.endsWith("/history")) body = [];
      else if (path.endsWith("/feedback")) {
        item.priority = "P4";
        if (newerVote)
          item.recommendations[0].feedback = {
            helpful: false,
            actor: "Engineer",
            updated_at: "2026-11-12T02:00:00Z",
          };
        await gate;
        body = {
          helpful: true,
          actor: "Engineer",
          updated_at: "2026-11-12T01:00:00Z",
        };
      } else if (path === "/api/incidents/event") body = item;
      await route.fulfill({ json: body });
    });
    await page.goto("/");
    await page.locator(".event-row").click();
    await page
      .locator(".recommendation")
      .getByRole("button", { name: "Помогла", exact: true })
      .click();
    await expect(page.locator(".detail-facts")).toContainText("P4", {
      timeout: 10000,
    });
    // The immediate refresh is held so that the mutation's local state is observable.
    await page.route("**/api/incidents/event", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 10000));
      await route.fulfill({ json: item });
    });
    if (newerVote)
      await expect(
        page.locator(".recommendation").getByRole("button", {
          name: "Не помогла",
          exact: true,
        }),
      ).toHaveAttribute("aria-pressed", "true");
    release();
    await expect(
      page.getByText("Сохраняем оценку…", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page
        .locator(".recommendation")
        .getByRole("button", {
          name: newerVote ? "Не помогла" : "Помогла",
          exact: true,
        }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".detail-facts")).toContainText("P4", {
      timeout: 200,
    });
  });
}

test("correction draft survives polling; feedback saves, fails and retries", async ({
  page,
}) => {
  const incident: any = {
    id: "event",
    title: "Disk full",
    description: "Диск заполнен",
    host: "host",
    severity: "critical",
    category: "server",
    priority: "P1",
    confidence: 0.9,
    needs_review: false,
    rationale: "Автоматически",
    lifecycle: "firing",
    handling: "new",
    first_seen: new Date().toISOString(),
    last_seen: new Date().toISOString(),
    labels: {},
    recommendation_status: "ready",
    recommendation_generation: 5,
    recommendations: [
      {
        id: "book",
        title: "Проверить диск",
        condition: "Диск заполнен",
        steps: ["Проверить место"],
        cautions: "",
        source: "Тест",
        category: "server",
        similarity: 0.8,
        revision: 1,
        matched_terms: ["диск"],
        explanation:
          "Лексические совпадения не объясняют решение векторной модели.",
        feedback: null,
      },
    ],
  };
  let fail = true;
  let failNextRead = false;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: any = {};
    if (path === "/api/auth/me")
      body = {
        id: "operator",
        name: "Инженер",
        email: "engineer@example.org",
        role: "engineer",
      };
    else if (path === "/api/summary")
      body = { critical: 1, warning: 0, info: 0, pending: 1, runbooks: 1 };
    else if (path === "/api/sources")
      body = {
        status: "online",
        source: "Prometheus",
        state: null,
        demo_mode: false,
      };
    else if (path.endsWith("/classification")) {
      Object.assign(incident, route.request().postDataJSON());
      incident.classification_correction = {
        actor: "Инженер",
        updated_at: new Date().toISOString(),
      };
      body = incident;
    } else if (path.endsWith("/feedback")) {
      if (fail) {
        fail = false;
        await route.fulfill({
          status: 503,
          json: { detail: "Сбой сохранения" },
        });
        return;
      }
      body = {
        helpful: route.request().postDataJSON().helpful,
        actor: "Инженер",
        updated_at: new Date().toISOString(),
      };
      incident.recommendations[0].feedback = body;
    } else if (path.endsWith("/history")) body = [];
    else if (path === "/api/incidents/event") {
      if (failNextRead) {
        failNextRead = false;
        await route.fulfill({
          status: 503,
          json: { detail: "Временная ошибка обновления" },
        });
        return;
      }
      body = incident;
    } else if (path === "/api/incidents")
      body = { items: [incident], total: 1 };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.locator(".event-row").click();
  await page
    .getByRole("button", { name: "Исправить классификацию", exact: true })
    .click();
  await page.getByLabel("Исправленный приоритет").selectOption("P2");
  await page
    .getByLabel("Комментарий к классификации")
    .fill("Проверено инженером");
  failNextRead = true;
  await expect(
    page.getByText("Временная ошибка обновления", { exact: true }),
  ).toBeVisible({ timeout: 10000 });
  await expect(page.getByLabel("Комментарий к классификации")).toHaveValue(
    "Проверено инженером",
  );
  await page.getByRole("button", { name: "Сохранить классификацию" }).click();
  await expect(page.locator(".classification-note")).toContainText(
    "Исправлено инженером",
  );
  await expect(page.locator(".detail-facts")).toContainText("P2");
  const rec = page.locator(".recommendation");
  await expect(rec).toContainText("диск");
  for (const name of ["Помогла", "Не помогла"]) {
    const height = await rec
      .getByRole("button", { name, exact: true })
      .evaluate((button) => button.getBoundingClientRect().height);
    expect(height).toBeLessThan(50);
  }
  await rec.getByRole("button", { name: "Помогла", exact: true }).click();
  await expect(rec).toContainText("Сбой сохранения");
  await rec.getByRole("button", { name: "Повторить оценку" }).click();
  await expect(
    rec.getByRole("button", { name: "Помогла", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await rec.getByRole("button", { name: "Не помогла", exact: true }).click();
  await expect(
    rec.getByRole("button", { name: "Не помогла", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(5500);
  await expect(
    rec.getByRole("button", { name: "Не помогла", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".current-state")).toHaveText("Ожидает решения");
});

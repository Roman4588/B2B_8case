import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page
    .getByLabel("Рабочий email")
    .fill(process.env.E2E_EMAIL || "e2e@example.org");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.E2E_PASSWORD || "Only-for-tests-2026");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "События", exact: true }),
  ).toBeVisible();
});

test("engineer inspects real alert and accepts manual action", async ({
  page,
}) => {
  test.setTimeout(120000);
  // Own a fresh real monitoring episode, rather than accepting an old action.
  expect(
    (
      await page.request.post("/api/demo", { data: { scenario: "normal" } })
    ).ok(),
  ).toBeTruthy();
  const postgres = async () => {
    expect((await page.request.post("/api/sources/sync")).ok()).toBeTruthy();
    return (
      await (
        await page.request.get("/api/incidents?q=PostgreSQL&state=firing")
      ).json()
    ).items;
  };
  await expect
    .poll(async () => (await postgres()).length, { timeout: 45000 })
    .toBe(0);
  expect(
    (
      await page.request.post("/api/demo", { data: { scenario: "outage" } })
    ).ok(),
  ).toBeTruthy();
  await expect
    .poll(async () => (await postgres())[0]?.handling, { timeout: 45000 })
    .toBe("new");
  await page.reload();
  const comment = `QA manual action ${Date.now()}`;
  const event = page
    .locator(".event-row")
    .filter({ hasText: "PostgreSQL" })
    .first();
  await expect(event).toBeVisible({ timeout: 45000 });
  await event.click();
  await expect(page.locator(".recommendation").first()).toBeVisible({
    timeout: 45000,
  });
  await expect(page.locator(".recommendation").first()).toContainText(
    "Источник:",
  );
  const accept = page.getByRole("button", {
    name: "Принято к ручному выполнению",
  });
  await page.getByLabel("Комментарий", { exact: true }).fill(comment);
  await accept.click();
  await expect(page.locator(".current-state")).toContainText(
    "Принято инженером",
  );
  await expect(
    page.getByRole("region", { name: "История решений" }),
  ).toContainText(comment);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Журнал действий" })
    .click();
  await expect(page.locator(".audit-list")).toContainText(comment);
});

test("knowledge form creates instruction and semantic search finds it", async ({
  page,
}) => {
  const title = `E2E: контроль свободного места ${Date.now()}`;
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "База знаний" })
    .click();
  await page.getByRole("button", { name: "Добавить инструкцию" }).click();
  await page.getByLabel("Название", { exact: true }).fill(title);
  await page
    .getByLabel("Если: описание события")
    .fill("На диске сервера закончилось свободное место, disk space full");
  await page
    .getByLabel("Действия: каждый шаг с новой строки")
    .fill("Проверить df -h\nСогласовать архивирование логов");
  await page.getByRole("button", { name: "Сохранить и индексировать" }).click();
  await expect(page.locator(".book").filter({ hasText: title })).toBeVisible();
  await expect(
    page.locator(".book").filter({ hasText: title }).locator(".job-status"),
  ).toHaveText("Готово", { timeout: 45000 });
  await page
    .getByLabel("Поиск регламентов")
    .fill("Диск заполнен, нужно проверить место");
  await page.getByRole("button", { name: "Найти", exact: true }).click();
  await expect(page.locator(".book-grid")).toContainText(
    /свободного места|место на диске/,
    { timeout: 30000 },
  );
});

test("mobile dashboard has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(
    page.getByRole("heading", { name: "События", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Источники" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Prometheus", exact: true }),
  ).toBeVisible();
});

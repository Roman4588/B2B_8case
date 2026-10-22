import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.OPERATOR_PASSWORD || "copilot-demo");
  await page.getByRole("button", { name: "Начать работу" }).click();
  await expect(
    page.getByRole("heading", { name: "Держите ситуацию под контролем." }),
  ).toBeVisible();
});

test("engineer inspects real alert and accepts manual action", async ({
  page,
}) => {
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
  if (await accept.count()) {
    await page
      .getByLabel("Комментарий", { exact: true })
      .fill("Проверка браузерного сценария: выполню вручную");
    await accept.click();
  }
  await expect(page.locator(".current-state")).toContainText(
    /Принято инженером|Выполнено вручную/,
  );
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Журнал действий" })
    .click();
  await expect(page.locator(".audit-list")).toContainText(
    "Принято к ручному выполнению",
  );
});

test("knowledge form creates instruction and semantic search finds it", async ({
  page,
}) => {
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "База знаний" })
    .click();
  await page.getByRole("button", { name: "Добавить инструкцию" }).click();
  await page
    .getByLabel("Название", { exact: true })
    .fill("E2E: контроль свободного места");
  await page
    .getByLabel("Если: описание события")
    .fill("На диске сервера закончилось свободное место, disk space full");
  await page
    .getByLabel("Действия: каждый шаг с новой строки")
    .fill("Проверить df -h\nСогласовать архивирование логов");
  await page.getByRole("button", { name: "Сохранить и индексировать" }).click();
  await expect(
    page.locator(".book").filter({ hasText: "E2E: контроль свободного места" }),
  ).toBeVisible();
  await expect(
    page
      .locator(".book")
      .filter({ hasText: "E2E: контроль свободного места" })
      .locator(".job-status"),
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
    page.getByRole("heading", { name: "Держите ситуацию под контролем." }),
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

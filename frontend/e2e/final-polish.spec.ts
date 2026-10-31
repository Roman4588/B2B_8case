import { test, expect, type Page } from "@playwright/test";
test.use({ hasTouch: true });

async function mount(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let json: unknown = {};
    if (url.pathname === "/api/auth/me")
      json = {
        id: "reviewer",
        name: "Инженер",
        role: "admin",
        is_active: true,
      };
    if (url.pathname === "/api/summary") json = { pending: 0, runbooks: 25 };
    if (url.pathname === "/api/incidents") json = { items: [], total: 0 };
    if (url.pathname === "/api/sources")
      json = {
        status: "online",
        interval_seconds: 15,
        state: { count: 0 },
        demo_mode: true,
      };
    if (url.pathname === "/api/health/ready")
      json = { status: "ready", indexed_runbooks: 25 };
    if (url.pathname === "/api/runbooks")
      json = {
        items: Array.from(
          { length: url.searchParams.get("q") ? 20 : 25 },
          (_, i) => ({
            id: `book-${i}`,
            title: `Инструкция ${i + 1}`,
            condition: "Проверка очереди",
            steps: ["Проверить"],
            category: "application",
            status: "ready",
            revision: 1,
            source: "team.md",
          }),
        ),
        semantic: !!url.searchParams.get("q"),
      };
    if (url.pathname === "/api/jobs")
      json = Array.from({ length: 25 }, (_, i) => ({
        id: `job-${i}`,
        filename: `Документ ${i + 1}.md`,
        status: "succeeded",
        progress: 1,
        total: 1,
      }));
    if (url.pathname === "/api/audit")
      json = Array.from({ length: 25 }, (_, i) => ({
        id: `audit-${i}`,
        actor: "Инженер",
        action: "accept",
        comment: `Запись ${i + 1}`,
        created_at: "2026-10-31T10:00:00Z",
      }));
    await route.fulfill({ json });
  });
  await page.goto("/");
  await expect(page.getByRole("navigation")).toBeVisible();
}

test("knowledge, document jobs and audit reveal ten more records without losing the remainder", async ({
  page,
}) => {
  await mount(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "База знаний", exact: true })
    .click();
  await expect(page.locator(".book-grid .book")).toHaveCount(10);
  await expect(page.locator(".jobs .job")).toHaveCount(10);
  await page
    .getByRole("button", { name: "Показать ещё инструкции", exact: true })
    .click();
  await expect(page.locator(".book-grid .book")).toHaveCount(20);
  await page
    .getByRole("button", { name: "Показать ещё инструкции", exact: true })
    .click();
  await expect(page.locator(".book-grid .book")).toHaveCount(25);
  await expect(
    page.getByRole("button", { name: "Показать ещё инструкции", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Показать ещё документы", exact: true })
    .click();
  await expect(page.locator(".jobs .job")).toHaveCount(20);
  await page
    .getByRole("textbox", { name: "Поиск регламентов" })
    .fill("Очередь");
  await page.getByRole("button", { name: "Найти", exact: true }).click();
  await expect(page.locator(".book-grid .book")).toHaveCount(10);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Журнал действий", exact: true })
    .click();
  await expect(page.locator(".audit-list article")).toHaveCount(10);
  await page
    .getByRole("button", { name: "Показать ещё записи", exact: true })
    .click();
  await expect(page.locator(".audit-list article")).toHaveCount(20);
  await page
    .getByRole("button", { name: "Показать ещё записи", exact: true })
    .click();
  await expect(page.locator(".audit-list article")).toHaveCount(25);
});

test("help is anchored, pinnable and dismissible; the empty event panel is centered", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);
  await expect(page.locator(".detail-placeholder")).toHaveCSS(
    "align-items",
    "center",
  );
  await expect(page.locator(".detail-placeholder")).toHaveCSS(
    "text-align",
    "center",
  );
  const help = page.getByRole("button", {
    name: "Как это работает",
    exact: true,
  });
  const before = await page.locator(".page-intro").boundingBox();
  await help.hover();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await expect(help).toHaveAccessibleDescription(/Откройте событие/);
  await help.click();
  await page.mouse.move(1000, 100);
  await expect(
    page.getByRole("dialog", { name: "Как устроена работа" }),
  ).toBeVisible();
  expect((await page.locator(".page-intro").boundingBox())?.y).toBe(before?.y);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(help).toBeFocused();
  await help.click();
  await page.getByRole("heading", { name: "События", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Источники", exact: true })
    .click();
  await expect(
    page.getByText("Инструкций в базе: 25", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Мониторинг проверяется отдельно/)).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("button", { name: "Проверить подключение", exact: true }),
  ).toHaveCSS("border-radius", "10px");
});

test("mobile help stays within the screen, survives a tap and closes explicitly", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await mount(page);
  await page
    .getByRole("button", { name: "Как это работает", exact: true })
    .tap();
  const popup = page.getByRole("dialog", { name: "Как устроена работа" });
  await expect(popup).toBeVisible();
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 740 });
    await expect
      .poll(async () => {
        const box = await popup.boundingBox();
        return (
          !!box &&
          box.x >= 12 &&
          box.x + box.width <= width - 12 &&
          box.y >= 12 &&
          box.y + box.height <= 728
        );
      })
      .toBe(true);
  }
  await page
    .getByRole("button", { name: "Закрыть подсказку", exact: true })
    .click();
  await expect(popup).toHaveCount(0);
});

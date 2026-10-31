import { test, expect, type Page } from "@playwright/test";

const operator = {
  id: "admin",
  name: "Демо-инженер",
  email: "preview@example.org",
  role: "admin",
  is_active: true,
  must_change_password: false,
};
const book = {
  id: "book",
  title: "Проверка PostgreSQL",
  condition: "Нет подключения к основному узлу",
  steps: ["Проверить доступность порта 5432"],
  cautions: "Согласуйте действия",
  category: "database",
  source: "Регламент команды",
  status: "ready",
  revision: 1,
};

async function mount(page: Page, role = "admin") {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let json: unknown = {};
    if (path === "/api/auth/me") json = { ...operator, role };
    else if (path === "/api/summary")
      json = { critical: 0, warning: 0, info: 0, pending: 0, runbooks: 1 };
    else if (path === "/api/incidents") json = { items: [], total: 0 };
    else if (path === "/api/sources")
      json = {
        source: "Prometheus",
        status: "online",
        interval_seconds: 15,
        stale_after_seconds: 60,
        demo_mode: true,
        state: { last_success: "2026-10-30T09:42:00Z", count: 0, error: "" },
      };
    else if (path === "/api/health/ready")
      json = { status: "ready", indexed_runbooks: 1 };
    else if (path === "/api/runbooks")
      json = { items: [book], semantic: false };
    else if (path === "/api/jobs") json = [];
    else if (path === "/api/audit")
      json = [
        {
          id: "audit",
          actor: "Демо-инженер",
          action: "accept",
          comment: "Проверяю состояние службы",
          created_at: "2026-10-30T09:42:00Z",
          incident_id: "event-01",
        },
      ];
    else if (path === "/api/users")
      json = [
        operator,
        {
          ...operator,
          id: "engineer",
          role: "engineer",
          name: "Инженер поддержки",
          email: "support@example.org",
        },
      ];
    await route.fulfill({ json });
  });
  await page.goto("/");
  await expect(page.locator(".app-shell")).toBeVisible();
}

async function navigate(page: Page, name: string) {
  await page
    .getByRole("navigation")
    .getByRole("button", { name, exact: true })
    .click();
}

test("login and mandatory password change keep their request contracts and validation", async ({
  page,
}) => {
  await mount(page);
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ status: 401, json: { detail: "Войдите в систему" } }),
  );
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({ json: { ...operator, must_change_password: true } }),
  );
  await page.route("**/api/auth/password", (route) =>
    route.fulfill({ json: operator }),
  );
  await page.reload();
  await page.getByLabel("Рабочий email").fill("preview@example.org");
  await page.getByLabel("Пароль", { exact: true }).fill("Temporary-pass-2026");
  await page
    .getByRole("button", { name: "Показать: Пароль", exact: true })
    .click();
  await expect(page.getByLabel("Пароль", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  const login = page.waitForRequest("**/api/auth/login");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  expect((await login).postDataJSON()).toEqual({
    email: "preview@example.org",
    password: "Temporary-pass-2026",
  });
  await expect(
    page.getByRole("heading", { name: "Задайте личный пароль" }),
  ).toBeVisible();
  await expect(page.locator(".app-shell")).toHaveCount(0);
  await page
    .getByLabel("Текущий пароль", { exact: true })
    .fill("Temporary-pass-2026");
  await page
    .getByLabel("Новый пароль", { exact: true })
    .fill("New-password-2026");
  await page
    .getByLabel("Повторите новый пароль", { exact: true })
    .fill("Different-password-2026");
  await page
    .getByRole("button", { name: "Сохранить пароль", exact: true })
    .click();
  await expect(page.getByRole("alert")).toHaveText("Пароли не совпадают");
  await page
    .getByLabel("Повторите новый пароль", { exact: true })
    .fill("New-password-2026");
  const change = page.waitForRequest("**/api/auth/password");
  await page
    .getByRole("button", { name: "Сохранить пароль", exact: true })
    .click();
  expect((await change).postDataJSON()).toEqual({
    current_password: "Temporary-pass-2026",
    new_password: "New-password-2026",
  });
  await expect(page.locator(".app-shell")).toBeVisible();
});

test("employee create, password reset and access confirmation preserve payloads", async ({
  page,
}) => {
  await mount(page);
  await navigate(page, "Сотрудники");
  await page
    .getByRole("button", { name: "Добавить сотрудника", exact: true })
    .click();
  await page
    .getByLabel("Имя сотрудника", { exact: true })
    .fill("Новый инженер");
  await page
    .getByLabel("Email сотрудника", { exact: true })
    .fill("new@example.org");
  await page
    .getByRole("combobox", { name: "Роль", exact: true })
    .selectOption("engineer");
  await page
    .getByLabel("Временный пароль", { exact: true })
    .fill("Temporary-pass-2026");
  const create = page.waitForRequest(
    (r) => r.url().endsWith("/api/users") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  expect((await create).postDataJSON()).toEqual({
    name: "Новый инженер",
    email: "new@example.org",
    role: "engineer",
    password: "Temporary-pass-2026",
  });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const engineer = page
    .locator(".employee-card")
    .filter({ hasText: "support@example.org" });
  await engineer
    .getByRole("button", { name: "Сбросить пароль", exact: true })
    .click();
  await page
    .getByLabel("Временный пароль", { exact: true })
    .fill("Reset-password-2026");
  const reset = page.waitForRequest("**/api/users/engineer/password");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  expect((await reset).postDataJSON()).toEqual({
    password: "Reset-password-2026",
  });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await engineer
    .getByRole("button", { name: "Отключить доступ", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Изменить доступ" }),
  ).toContainText("Все сессии сотрудника будут завершены");
  const toggle = page.waitForRequest(
    (r) => r.url().endsWith("/api/users/engineer") && r.method() === "PATCH",
  );
  await page.getByRole("button", { name: "Подтвердить", exact: true }).click();
  expect((await toggle).postDataJSON()).toEqual({ is_active: false });
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("knowledge search, edit and import preserve request contracts", async ({
  page,
}) => {
  await mount(page);
  await navigate(page, "База знаний");
  await expect(page.locator(".book")).toContainText(book.title);
  await page.getByLabel("Поиск регламентов").fill("Проверка основного узла");
  const search = page.waitForRequest(
    (r) => new URL(r.url()).searchParams.get("q") === "Проверка основного узла",
  );
  await page.getByRole("button", { name: "Найти", exact: true }).click();
  await search;
  await page.getByRole("button", { name: "Открыть", exact: true }).click();
  await expect(page.getByLabel("Название", { exact: true })).toHaveValue(
    book.title,
  );
  await page
    .getByLabel("Название", { exact: true })
    .fill("Обновлённая проверка PostgreSQL");
  const edit = page.waitForRequest(
    (r) => r.url().endsWith("/api/runbooks/book") && r.method() === "PATCH",
  );
  await page
    .getByRole("button", { name: "Сохранить и индексировать", exact: true })
    .click();
  expect((await edit).postDataJSON()).toEqual({
    title: "Обновлённая проверка PostgreSQL",
    condition: book.condition,
    steps: book.steps,
    cautions: book.cautions,
    category: book.category,
  });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const upload = page.waitForRequest("**/api/runbooks/import");
  await page
    .locator('input[type="file"]')
    .setInputFiles({
      name: "reglament.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# Проверка\nПроверить доступность узла"),
    });
  const request = await upload;
  expect(request.method()).toBe("POST");
  expect(request.headers()["content-type"]).toContain("multipart/form-data");
  expect(request.postDataBuffer()?.toString()).toContain("reglament.md");
  await expect(page.getByRole("status")).toContainText("Документ принят");
});

test("source sync and demo controls retain actions and stale warnings", async ({
  page,
}) => {
  await mount(page);
  await navigate(page, "Источники");
  const sync = page.waitForRequest("**/api/sources/sync");
  await page
    .getByRole("button", { name: "Проверить подключение", exact: true })
    .click();
  expect((await sync).method()).toBe("POST");
  for (const [label, value] of [
    ["Аварийные события", "outage"],
    ["Предупреждения", "warning"],
    ["Восстановление", "normal"],
  ]) {
    const demo = page.waitForRequest("**/api/demo");
    await page.getByRole("button", { name: label, exact: true }).click();
    expect((await demo).postDataJSON()).toEqual({ scenario: value });
  }
  await page.route("**/api/sources", (route) =>
    route.fulfill({
      json: {
        source: "Prometheus",
        status: "stale",
        interval_seconds: 15,
        demo_mode: true,
        state: { last_success: "2026-10-30T09:42:00Z", count: 0, error: "" },
      },
    }),
  );
  await navigate(page, "События");
  await navigate(page, "Источники");
  await expect(page.getByRole("alert")).toContainText(
    "Показанные события могут быть устаревшими",
  );
});

test("engineer role cannot see employee administration", async ({ page }) => {
  await mount(page, "engineer");
  await expect(
    page
      .getByRole("navigation")
      .getByRole("button", { name: "Сотрудники", exact: true }),
  ).toHaveCount(0);
  await navigate(page, "Мой профиль");
  await expect(
    page.getByLabel("Текущий пароль", { exact: true }),
  ).toBeVisible();
});

test("all sections and dialogs fit narrow screens without hidden overflow", async ({
  page,
}) => {
  await mount(page);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const width of [320, 375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const section of [
      "База знаний",
      "Источники",
      "Журнал действий",
      "Сотрудники",
      "Мой профиль",
    ]) {
      await navigate(page, section);
      const overflow = await page
        .locator(".main-content")
        .evaluate((el) => el.scrollWidth > el.clientWidth);
      expect(overflow, `${section} at ${width}px`).toBe(false);
      if (section === "База знаний" || section === "Сотрудники") {
        await page
          .getByRole("button", {
            name:
              section === "База знаний"
                ? "Добавить инструкцию"
                : "Добавить сотрудника",
            exact: true,
          })
          .click();
        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();
        expect(
          await dialog.evaluate((el) => el.scrollWidth > el.clientWidth),
          `Dialog at ${width}px`,
        ).toBe(false);
        await page.getByRole("button", { name: "Отмена", exact: true }).click();
      }
    }
  }
  expect(errors).toEqual([]);
});

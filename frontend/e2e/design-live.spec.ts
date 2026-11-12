import { test, expect } from "@playwright/test";
import path from "node:path";

test("real backend: responsive screens, persistent drafts and keyboard return", async ({
  page,
}) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page
    .getByLabel("Рабочий email")
    .fill(process.env.E2E_EMAIL || "e2e@example.org");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.E2E_PASSWORD || "Only-for-tests-2026");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.locator(".event-row").first()).toBeVisible();
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    const capture = async (name: string) => {
      await page.screenshot({
        path: path.resolve(`../outputs/design-after-${name}-${width}.png`),
        fullPage: false,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${name} ${width}: overflow`,
      ).toBe(true);
    };
    await capture("events");
    const row = page.locator(".event-row").first();
    await row.click();
    await expect(page.locator(".detail-title")).toBeVisible();
    await capture("detail");
    if (width <= 1100) {
      await page.locator(".detail-panel").focus();
      await page.keyboard.press("Shift+Tab");
      await page.keyboard.press("Tab");
      expect(
        await page
          .locator(".detail-panel")
          .evaluate((el) => el.contains(document.activeElement)),
      ).toBe(true);
    }
    await page
      .getByRole("button", { name: "Исправить классификацию", exact: true })
      .click();
    await page
      .getByLabel("Комментарий к классификации")
      .fill("Черновик: проверка длинного русского комментария без сохранения");
    await page.getByLabel("Исправленный приоритет").selectOption("P3");
    await page.getByLabel("Комментарий к классификации").focus();
    await page.waitForTimeout(5500);
    await expect(page.getByLabel("Комментарий к классификации")).toBeFocused();
    await expect(page.getByLabel("Исправленный приоритет")).toHaveValue("P3");
    await capture("classification");
    await page.keyboard.press("Escape");
    await expect(page.locator(".feedback-form")).toHaveCount(0);
    const reading = page.getByRole("region", { name: "Разбор и рекомендации" });
    await reading.evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    await expect(page.locator(".manual-controls")).toBeInViewport();
    await page.keyboard.press("Escape");
    await expect(row).toBeFocused();
    for (const [name, key, ready] of [
      ["База знаний", "knowledge", ".book"],
      ["Источники", "sources", ".source-card"],
      ["Журнал действий", "audit", ".audit-record"],
      ["Сотрудники", "users", ".employee-card"],
      ["Мой профиль", "profile", ".account-form"],
    ]) {
      await page
        .getByRole("navigation")
        .getByRole("button", { name, exact: true })
        .click();
      await expect(page.locator(ready).first()).toBeVisible();
      await capture(key);
    }
    await page
      .getByRole("navigation")
      .getByRole("button", { name: /^События/ })
      .click();
    await expect(page.locator(".event-row").first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

// Captures the same local fixtures and viewport for before/after comparison.
import { chromium, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const phase = process.argv[2];
if (!["before", "after"].includes(phase)) throw Error("Use before or after");
const base = "http://127.0.0.1:5173";
if (!(await (await fetch(base)).text()).includes('id="design-preview-note"'))
  throw Error("Local preview required");
const output = fileURLToPath(
  new URL(`../../.hallmark/rollout/${phase}/`, import.meta.url),
);
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  timezoneId: "Asia/Tomsk",
  reducedMotion: "reduce",
});
await page.goto(base);
await page.locator(".event-row").first().waitFor();
const capture = async (name) => {
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path: output + name + "-desktop.png" });
  await page.setViewportSize({ width: 375, height: 900 });
  await page.screenshot({
    path: output + name + "-mobile.png",
    fullPage: true,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  if (overflow) throw Error(`Mobile overflow: ${name}`);
  await page.setViewportSize({ width: 1440, height: 1000 });
};
for (const [name, label, ready] of [
  ["knowledge", "База знаний", ".book"],
  ["sources", "Источники", ".source-card"],
  ["audit", "Журнал действий", ".audit-list article"],
  ["employees", "Сотрудники", ".employee-card"],
  ["profile", "Мой профиль", ".password-panel"],
]) {
  await page
    .getByRole("navigation")
    .getByRole("button", { name: label, exact: true })
    .click();
  await page.locator(ready).first().waitFor();
  await capture(name);
  if (name === "knowledge") {
    await page
      .getByRole("button", { name: "Добавить инструкцию", exact: true })
      .click();
    await capture("knowledge-editor");
    await page.getByLabel("Закрыть форму").click();
  }
  if (name === "employees") {
    await page
      .getByRole("button", { name: "Добавить сотрудника", exact: true })
      .click();
    await capture("employee-editor");
    await page.getByRole("button", { name: "Отмена", exact: true }).click();
  }
}
await page.getByRole("button", { name: "Выйти", exact: true }).click();
await expect(page.getByLabel("Рабочий email")).toBeVisible();
await page.getByLabel("Рабочий email").fill("preview@example.org");
await capture("login");
await page.getByLabel("Пароль", { exact: true }).fill("Preview-only-2026");
await page.getByRole("button", { name: "Войти", exact: true }).click();
await expect(page.locator(".app-shell")).toBeVisible();
await browser.close();
console.log(`Saved 8 matched ${phase} desktop/mobile pairs in ${output}`);

// Run only against scripts/preview-design.mjs; this check changes its in-memory fixtures.
import { chromium, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const base = "http://127.0.0.1:5173";
const marker = await (await fetch(base)).text();
if (!marker.includes('id="design-preview-note"'))
  throw Error(
    "Local design preview required; never run this check on a real server.",
  );
const output = fileURLToPath(
  new URL("../../.hallmark/screens/", import.meta.url),
);
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  timezoneId: "Asia/Tomsk",
});
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
await page.goto(base);
await expect(page.locator(".event-row")).toHaveCount(6);
await page.screenshot({ path: output + "events-desktop.png" });
await page.locator(".event-row").first().click();
await expect(page.locator(".recommendation")).toBeVisible();
await page.screenshot({ path: output + "incident-desktop.png" });
const widths = [];
for (const width of [320, 375, 700, 768, 1024, 1280, 1440, 1920]) {
  await page.setViewportSize({ width, height: 900 });
  await expect(page.getByLabel("Закрыть событие")).toBeVisible();
  const overflow = await page.evaluate(() => {
    const panel = document.querySelector(".detail-panel");
    return {
      page: document.documentElement.scrollWidth > innerWidth,
      panel: panel.scrollWidth > panel.clientWidth,
    };
  });
  if (overflow.page || overflow.panel)
    throw Error(`Overflow at ${width}: ${JSON.stringify(overflow)}`);
  widths.push({ width, overflow: false });
  if (width === 375)
    await page.screenshot({ path: output + "incident-mobile.png" });
}
await page.setViewportSize({ width: 1440, height: 1000 });
await page
  .getByLabel("Комментарий", { exact: true })
  .fill("Проверка нового интерфейса на локальных тестовых данных");
const actionRequest = page.waitForRequest(
  (request) =>
    request.url().endsWith("/actions") && request.method() === "POST",
);
await page
  .getByRole("button", { name: "Принято к ручному выполнению", exact: true })
  .click();
expect((await actionRequest).postDataJSON()).toEqual({
  action: "accept",
  comment: "Проверка нового интерфейса на локальных тестовых данных",
});
await expect(page.locator(".current-state")).toHaveText("Принято инженером");
await expect(
  page.getByRole("region", { name: "История решений" }),
).toContainText("Проверка нового интерфейса");
await page
  .getByRole("button", { name: "Выполнено вручную", exact: true })
  .click();
await expect(page.locator(".current-state")).toHaveText("Выполнено вручную");
await page.getByLabel("Закрыть событие").click();
await page.getByLabel("Поиск событий").fill("несуществующий-хост");
await expect(page.locator(".empty")).toBeVisible();
await page.screenshot({ path: output + "events-empty.png" });
await page.getByLabel("Поиск событий").fill("");
await expect(page.locator(".event-row")).toHaveCount(6);
await page.setViewportSize({ width: 375, height: 900 });
await page.getByRole("button", { name: "Как это работает" }).click();
await expect(page.locator(".help-banner")).toBeVisible();
await page.getByRole("button", { name: "Понятно", exact: true }).click();
await page.screenshot({ path: output + "events-mobile.png", fullPage: true });
if (errors.length) throw Error(errors.join("\n"));
writeFileSync(
  output + "verification.json",
  JSON.stringify(
    {
      widths,
      actionPayload: "preserved",
      accept: "passed",
      complete: "passed",
      history: "passed",
      empty: "passed",
      mobileHelp: "passed",
      pageErrors: errors,
    },
    null,
    2,
  ),
);
await browser.close();
console.log(
  "Passed: 8 widths, accept/complete, request payload, history, empty state, mobile help; no page errors.",
);

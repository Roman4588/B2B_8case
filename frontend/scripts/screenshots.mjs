import { chromium } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const base = process.env.BASE_URL || "http://localhost:8080";
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1100 },
});
await context.request.post(base + "/api/auth/login", {
  data: { password: process.env.OPERATOR_PASSWORD || "copilot-demo" },
});
await context.request.post(base + "/api/demo", {
  data: { scenario: "outage" },
});
for (let i = 0; i < 30; i++) {
  const summary = await (
    await context.request.get(base + "/api/summary")
  ).json();
  if (summary.critical >= 2) break;
  await new Promise((resolve) => setTimeout(resolve, 1500));
}
const page = await context.newPage();
await page.goto(base);
await page.locator(".event-row").first().waitFor();
await page.screenshot({ path: path.join(root, "docs/media/dashboard.png") });
await page
  .locator(".event-row")
  .filter({ hasText: "PostgreSQL" })
  .first()
  .click();
await page.locator(".recommendation").first().waitFor();
await page.locator(".recommendation").first().scrollIntoViewIfNeeded();
await page.screenshot({ path: path.join(root, "docs/media/incident.png") });
await page.getByLabel("Закрыть событие").click();
await page.setViewportSize({ width: 375, height: 812 });
await page.evaluate(() => scrollTo(0, 0));
if (
  await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
)
  throw Error("Horizontal overflow");
await page.screenshot({
  path: path.join(root, "docs/media/mobile.png"),
  fullPage: true,
});
console.log(
  "Saved desktop, recommendation and mobile screenshots. No horizontal overflow.",
);
await browser.close();

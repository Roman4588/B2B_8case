import { chromium, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const phase = process.argv[2];
if (!["before", "after"].includes(phase)) throw Error("Use before or after");
const base = process.env.BASE_URL || "http://127.0.0.1:5184";
if (!(await (await fetch(base)).text()).includes('id="design-preview-note"'))
  throw Error("Fixture-only design preview required");
const output = fileURLToPath(
  new URL(`../../.hallmark/incident-panel/${phase}/`, import.meta.url),
);
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    timezoneId: "Asia/Tomsk",
    reducedMotion: "reduce",
  });
  await page.goto(base);
  await page.locator(".event-row").first().click();
  await expect(page.locator(".recommendation").first()).toBeVisible();
  const metrics = [];
  for (const [name, width, height] of [
    ["desktop", 1440, 1000],
    ["laptop", 1440, 900],
    ["mobile", 375, 900],
  ]) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => {
      scrollTo(0, 0);
      document.querySelector(".detail-panel").scrollTop = 0;
    });
    await page.screenshot({ path: `${output}/${name}.png` });
    metrics.push(
      await page
        .getByRole("button", {
          name: "Принято к ручному выполнению",
          exact: true,
        })
        .evaluate(
          (button, viewport) => {
            const r = button.getBoundingClientRect();
            return {
              ...viewport,
              action_top: Math.round(r.top),
              action_bottom: Math.round(r.bottom),
              visible_without_scroll: r.top >= 0 && r.bottom <= innerHeight,
            };
          },
          { width, height },
        ),
    );
  }
  writeFileSync(`${output}/metrics.json`, JSON.stringify(metrics, null, 2));
  console.log(JSON.stringify(metrics));
} finally {
  await browser.close();
}

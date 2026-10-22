import { chromium } from "@playwright/test";
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 375, height: 812 },
});
const base = process.env.BASE_URL || "http://localhost:8080";
await context.request.post(base + "/api/auth/login", {
  data: { password: "copilot-demo" },
});
const page = await context.newPage();
await page.goto(base);
await page.locator(".stats-grid").waitFor();
console.log(
  await page.evaluate(() => ({
    width: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    overflow: [...document.querySelectorAll("body *")]
      .filter((e) => e.getBoundingClientRect().right > innerWidth + 1)
      .map((e) => ({
        tag: e.tagName,
        class: e.className,
        right: Math.round(e.getBoundingClientRect().right),
        text: e.textContent?.slice(0, 60),
      }))
      .slice(0, 20),
  })),
);
await page.screenshot({ path: "../docs/media/mobile.png", fullPage: true });
await browser.close();

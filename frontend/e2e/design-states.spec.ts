import { test, expect } from "@playwright/test";
import path from "node:path";

test("login layouts and semantic palette contrast", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Рабочий email")).toBeVisible();
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({
      path: path.resolve(`../outputs/design-after-login-${width}.png`),
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  const ratios = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    const ctx = canvas.getContext("2d")!;
    const luminance = (token: string) => {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = style.getPropertyValue(token).trim();
      ctx.fillRect(0, 0, 1, 1);
      const rgb = Array.from(ctx.getImageData(0, 0, 1, 1).data)
        .slice(0, 3)
        .map((x) => {
          const v = x / 255;
          return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
        });
      return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
    };
    return [
      ["--color-ink", "--color-paper"],
      ["--color-ink-2", "--color-paper"],
      ["--color-muted", "--color-paper-2"],
      ["--color-accent-ink", "--color-accent"],
      ["--color-critical", "--color-critical-bg"],
      ["--color-warning", "--color-warning-bg"],
      ["--color-info", "--color-info-bg"],
      ["--color-success", "--color-success-bg"],
      ["--color-nav-muted", "--color-nav"],
      ["--color-focus", "--color-paper"],
    ].map(([ink, paper]) => {
      const a = luminance(ink),
        b = luminance(paper);
      return {
        ink,
        paper,
        ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05),
      };
    });
  });
  for (const pair of ratios)
    expect(pair.ratio, `${pair.ink} / ${pair.paper}`).toBeGreaterThanOrEqual(
      4.5,
    );
  await test
    .info()
    .attach("contrast", {
      body: JSON.stringify(ratios, null, 2),
      contentType: "application/json",
    });
});

test("long Russian event title, descriptions and short landscape remain operable", async ({
  page,
}) => {
  const item = {
    id: "stress",
    title:
      "Недоступность основного сервера обработки финансовых документов в распределённой инфраструктуре предприятия: требуется проверка доступности и состояния репликации ".repeat(
        3,
      ),
    description:
      "Длинное описание события с русскими названиями и диагностической информацией. ".repeat(
        60,
      ),
    host: "очень-длинное-имя-основного-сервера.example.internal",
    severity: "critical",
    category: "database",
    priority: "P1",
    confidence: 0.8,
    needs_review: true,
    rationale: "Проверьте причину вручную.",
    lifecycle: "firing",
    handling: "new",
    first_seen: "2026-11-12T01:00:00Z",
    recommendation_status: "ready",
    recommendations: [],
    recommendation_generation: 1,
  };
  await page.route("**/api/**", (route) => {
    const p = new URL(route.request().url()).pathname;
    const json =
      p === "/api/auth/me"
        ? { id: "stress-user", name: "Инженер", role: "admin" }
        : p === "/api/summary"
          ? { critical: 1, runbooks: 0, pending: 1 }
          : p === "/api/sources"
            ? { status: "online", state: {} }
            : p === "/api/incidents"
              ? { items: [item], total: 1 }
              : p.endsWith("/history")
                ? []
                : item;
    return route.fulfill({ json });
  });
  for (const [width, height] of [
    [1440, 900],
    [1024, 768],
    [768, 1024],
    [390, 844],
    [320, 360],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto("/");
    await page.locator(".event-row").click();
    const comment = page.getByLabel("Комментарий", { exact: true });
    await comment.scrollIntoViewIfNeeded();
    await expect(comment).toBeInViewport({ ratio: 1 });
    const accept = page.getByRole("button", {
      name: "Принято к ручному выполнению",
      exact: true,
    });
    await accept.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.resolve(`../outputs/design-stress-${width}-${height}.png`),
    });
    await expect(accept).toBeInViewport({ ratio: 1 });
    expect(
      await page
        .locator(".detail-panel")
        .evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await page.screenshot({
      path: path.resolve(`../outputs/design-stress-${width}-${height}.png`),
    });
  }
});

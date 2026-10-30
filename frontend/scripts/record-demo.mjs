import { chromium } from "@playwright/test";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const audio = process.env.DEMO_AUDIO_DIR || path.join(root, "outputs/demo-audio");
const output =
  process.env.DEMO_OUTPUT_DIR || path.join(root, "outputs/demo-recording");
await mkdir(output, { recursive: true });
await mkdir(path.join(root, "docs/media"), { recursive: true });
const story = JSON.parse(
  await readFile(path.join(root, "demo/storyboard.json"), "utf8"),
);
function duration(wav) {
  let rate = 0,
    length = 0;
  for (let p = 12; p + 8 < wav.length;) {
    const size = wav.readUInt32LE(p + 4);
    const type = wav.toString("ascii", p, p + 4);
    if (type === "fmt ") rate = wav.readUInt32LE(p + 16);
    if (type === "data") {
      length = size;
      break;
    }
    p += 8 + size + (size % 2);
  }
  if (!rate || !length) throw Error("Invalid WAV");
  return length / rate;
}
for (let i = 0; i < story.length; i++)
  story[i].seconds = duration(
    await readFile(path.join(audio, String(i).padStart(2, "0") + ".wav")),
  );
const total = story.reduce((n, s) => n + s.seconds, 0);
if (total > 295) throw Error(`Demo longer than five minutes: ${total}`);
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: output, size: { width: 1440, height: 900 } },
});
const base = process.env.BASE_URL || "http://localhost:8080";
if (!process.env.E2E_EMAIL || !process.env.E2E_PASSWORD)
  throw Error("Set E2E_EMAIL and E2E_PASSWORD for the recording account");
const login = await context.request.post(base + "/api/auth/login", {
  data: { email: process.env.E2E_EMAIL, password: process.env.E2E_PASSWORD },
});
if (!login.ok()) throw Error(`Recording login failed: ${login.status()}`);
await context.request.post(base + "/api/demo", {
  data: { scenario: "normal" },
});
async function waitCount(expected) {
  for (let i = 0; i < 30; i++) {
    const data = await (
      await context.request.get(base + "/api/summary")
    ).json();
    if (expected(data)) return;
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw Error("Prometheus did not update");
}
await waitCount((v) => v.critical === 0);
await context.request.post(base + "/api/demo", {
  data: { scenario: "outage" },
});
await waitCount((v) => v.critical >= 2);
const page = await context.newPage();
const video = page.video();
const card = (title, sub, body) =>
  `<html lang="ru"><body style="margin:0;background:#102938;color:#dcefe3;font-family:Segoe UI,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center"><div style="width:1120px"><p style="font-size:16px;letter-spacing:5px;color:#83b39a">КЕЙС 08 · AI OPERATIONS COPILOT</p><h1 style="font-size:66px;font-weight:500;letter-spacing:-2px;line-height:1.15;margin:30px 0">${title}</h1><p style="font-size:24px;color:#a3beb6">${sub}</p><div style="font-size:22px;line-height:1.9;color:#b8d3c6;margin-top:40px">${body}</div><p style="font-size:14px;color:#77988e;margin-top:45px">github.com/Roman4588/B2B_8case</p></div></body></html>`;
async function caption(s) {
  await page.evaluate(({ title, caption }) => {
    document.getElementById("demo-caption")?.remove();
    const bar = document.createElement("div");
    bar.id = "demo-caption";
    bar.style.cssText =
      "position:fixed;bottom:0;left:0;right:0;z-index:9999;background:#102938f5;color:#fff;padding:18px 35px;border-top:2px solid #95c7ad;box-shadow:0 -10px 30px #10293822;pointer-events:none;font-family:Segoe UI,sans-serif";
    const heading = document.createElement("strong");
    heading.textContent = title;
    heading.style.cssText =
      "display:block;font-size:21px;font-weight:500;margin-bottom:6px";
    const text = document.createElement("span");
    text.textContent = caption;
    text.style.cssText = "font-size:16px;color:#abc9ba";
    bar.append(heading, text);
    document.body.append(bar);
  }, s);
}
for (const [index, s] of story.entries()) {
  const started = Date.now();
  console.log(
    `Scene ${index + 1}/${story.length}: ${s.id}, ${s.seconds.toFixed(1)} s`,
  );
  if (s.id === "team")
    await page.setContent(
      card(
        "Дейкстра",
        "ИИ-Ассистент Дежурного",
        "Диль Роман · Мадаминов Дамир · Родиков Глеб<br/>Шабалин Максим · Иудин Никита",
      ),
    );
  if (s.id === "dashboard") {
    await page.goto(base);
    await page.locator(".event-row").first().waitFor();
    await caption(s);
  }
  if (s.id === "incident") {
    await page
      .locator(".event-row")
      .filter({ hasText: "PostgreSQL" })
      .first()
      .click();
    await page.locator(".recommendation").first().waitFor();
    await page.screenshot({
      path: path.join(root, "docs/media/dashboard.png"),
    });
    await caption(s);
    await page.waitForTimeout(4000);
    await page.locator(".recommendation").first().scrollIntoViewIfNeeded();
  }
  if (s.id === "manual") {
    const input = page.getByLabel("Комментарий", { exact: true });
    await input.scrollIntoViewIfNeeded();
    await input.fill(
      "Команда Дейкстра: проверим основной узел и согласуем восстановление с администратором БД.",
    );
    await page
      .getByRole("button", { name: "Принято к ручному выполнению" })
      .click();
    await page.waitForTimeout(1200);
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "Журнал действий" })
      .click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await caption(s);
  }
  if (s.id === "knowledge") {
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "База знаний" })
      .click();
    await page
      .getByLabel("Поиск регламентов")
      .fill("Не отвечает основной узел PostgreSQL");
    await page.getByRole("button", { name: "Найти", exact: true }).click();
    await page.locator(".book").first().waitFor();
    await caption(s);
  }
  if (s.id === "sources") {
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "Источники" })
      .click();
    await page
      .getByRole("button", { name: "Восстановление", exact: true })
      .click();
    await caption(s);
  }
  if (s.id === "recovery") {
    await waitCount((v) => v.critical === 0);
    await page
      .getByRole("navigation")
      .getByRole("button", { name: /^События/ })
      .click();
    await page.getByLabel("Состояние событий").selectOption("resolved");
    await page.locator(".event-row").first().waitFor();
    await caption(s);
  }
  if (s.id === "finish")
    await page.setContent(
      card(
        "Решение за инженером.",
        "Ассистент помогает разобраться и найти проверенный регламент.",
        'React + TypeScript · FastAPI<br/>PostgreSQL / pgvector · Celery / Redis · Prometheus<br/><span style="color:#90c4a6">Запуск: docker-compose up --build</span>',
      ),
    );
  await page.waitForTimeout(
    Math.max(0, s.seconds * 1000 - (Date.now() - started)),
  );
}
await context.close();
await browser.close();
const file = await video.path();
await writeFile(
  path.join(output, "recording.json"),
  JSON.stringify(
    { video: file, total_seconds: total, segments: story },
    null,
    2,
  ),
);
const linux = (p) =>
  "/mnt/" + p[0].toLowerCase() + p.slice(2).replaceAll("\\", "/");
await writeFile(
  path.join(output, "audio-list.txt"),
  story
    .map(
      (_, i) =>
        `file '${linux(path.join(audio, String(i).padStart(2, "0") + ".wav"))}'`,
    )
    .join("\n"),
);
console.log(JSON.stringify({ video: file, seconds: total, output }, null, 2));

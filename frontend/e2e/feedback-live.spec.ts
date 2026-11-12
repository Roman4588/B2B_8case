import { test, expect } from "@playwright/test";

test("real stack persists corrections, feedback, aggregates and audit", async ({
  page,
}) => {
  test.setTimeout(120000);
  await page.goto("/");
  await page
    .getByLabel("Рабочий email")
    .fill(process.env.E2E_EMAIL || "e2e@example.org");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.E2E_PASSWORD || "Only-for-tests-2026");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("heading", { name: "События" })).toBeVisible();
  // Own the instruction that this scenario deletes; never consume the seed corpus.
  const fixtureTitle = `QA feedback ${Date.now()}`;
  const created = await page.request.post("/api/runbooks", {
    data: {
      title: fixtureTitle,
      condition:
        "PostgreSQL primary database is down, connection refused, database unavailable. База данных PostgreSQL недоступна; нет соединения с основным узлом.",
      category: "database",
      steps: ["Проверить доступность порта 5432"],
      cautions: "Только учебная проверка",
    },
  });
  expect(created.status()).toBe(202);
  const fixture = await created.json();
  await expect
    .poll(
      async () => {
        const books = (await (await page.request.get("/api/runbooks")).json())
          .items;
        return books.find((book: any) => book.id === fixture.id)?.status;
      },
      { timeout: 60000 },
    )
    .toBe("ready");
  expect(
    (
      await page.request.post("/api/demo", { data: { scenario: "outage" } })
    ).ok(),
  ).toBeTruthy();
  expect((await page.request.post("/api/sources/sync")).ok()).toBeTruthy();
  const row = page
    .locator(".event-row")
    .filter({ hasText: "PostgreSQL" })
    .first();
  await expect(row).toBeVisible({ timeout: 45000 });
  await row.click();
  await page
    .getByRole("button", { name: "Исправить классификацию", exact: true })
    .click();
  await page.getByLabel("Исправленный тип").selectOption("warning");
  await page.getByLabel("Исправленная категория").selectOption("database");
  await page.getByLabel("Исправленный приоритет").selectOption("P2");
  await page
    .getByLabel("Комментарий к классификации")
    .fill("E2E: проверено инженером");
  await page.getByRole("button", { name: "Сохранить классификацию" }).click();
  await expect(page.locator(".classification-note")).toContainText(
    "Исправлено инженером",
  );
  await expect(page.locator(".detail-facts")).toContainText("P2");
  const rec = page.locator(".recommendation").filter({ hasText: fixtureTitle });
  await expect(rec).toBeVisible({ timeout: 45000 });
  await expect(rec.locator(".recommendation-explanation")).toContainText(
    "не вероятность правильности",
  );
  await rec.getByRole("button", { name: "Помогла", exact: true }).click();
  await expect(
    rec.getByRole("button", { name: "Помогла", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const events = await (
    await page.request.get("/api/incidents?q=PostgreSQL&state=firing")
  ).json();
  const detail = await (
    await page.request.get(`/api/incidents/${events.items[0].id}`)
  ).json();
  const recommendation = detail.recommendations.find(
    (item: any) => item.id === fixture.id,
  );
  expect(recommendation).toBeTruthy();
  expect(recommendation.feedback.helpful).toBe(true);
  const books = async () =>
    (await (await page.request.get("/api/runbooks")).json()).items.find(
      (book: any) => book.id === recommendation.id,
    );
  const afterTrue = await books();
  expect(
    (
      await page.request.put(
        `/api/incidents/${detail.id}/recommendations/${recommendation.id}/feedback`,
        {
          data: {
            helpful: true,
            revision: recommendation.revision,
            generation: detail.recommendation_generation,
          },
        },
      )
    ).ok(),
  ).toBeTruthy();
  expect((await books()).helpful_count).toBe(afterTrue.helpful_count);
  await rec.getByRole("button", { name: "Не помогла", exact: true }).click();
  await expect(
    rec.getByRole("button", { name: "Не помогла", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const afterFalse = await books();
  expect(afterFalse.helpful_count).toBe(afterTrue.helpful_count - 1);
  expect(afterFalse.not_helpful_count).toBe(afterTrue.not_helpful_count + 1);
  const audit = await (
    await page.request.get(`/api/incidents/${detail.id}/history`)
  ).json();
  expect(
    audit.some((entry: any) => entry.action === "classification_corrected"),
  ).toBe(true);
  expect(
    audit.some((entry: any) => entry.action === "recommendation_feedback"),
  ).toBe(true);
  await page.reload();
  await page
    .locator(".event-row")
    .filter({ hasText: "PostgreSQL" })
    .first()
    .click();
  await expect(page.locator(".classification-note")).toContainText(
    "Исправлено инженером",
  );
  await expect(
    page
      .locator(".recommendation")
      .filter({ hasText: fixtureTitle })
      .getByRole("button", { name: "Не помогла", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({
    path: "test-results/feedback-live-card.png",
    fullPage: true,
  });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "База знаний" })
    .click();
  await expect(
    page.locator(".book").filter({ hasText: recommendation.title }).first(),
  ).toContainText("По всем редакциям регламента");

  // Delete a genuinely rated instruction through the current confirmation flow.
  await page
    .getByRole("button", {
      name: `Удалить инструкцию ${recommendation.title}`,
      exact: true,
    })
    .click();
  const deleteBook = page.waitForResponse(
    (response) =>
      response.request().method() === "DELETE" &&
      response.url().endsWith(`/runbooks/${recommendation.id}`),
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Удалить", exact: true })
    .click();
  expect((await deleteBook).status()).toBe(200);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.locator(".book").filter({ hasText: recommendation.title }),
  ).toHaveCount(0);

  // Real upload, worker processing and document deletion; no API interception.
  const filename = `feedback-import-${Date.now()}.json`;
  const title = `QA import ${Date.now()}`;
  await page.locator('input[type="file"]').setInputFiles({
    name: filename,
    mimeType: "application/json",
    buffer: Buffer.from(
      JSON.stringify([
        {
          title,
          condition: "PostgreSQL primary is down",
          steps: ["Проверить доступность порта"],
          category: "database",
        },
      ]),
    ),
  });
  let job: any;
  await expect
    .poll(
      async () => {
        const jobs = await (await page.request.get("/api/jobs")).json();
        job = jobs.find((entry: any) => entry.filename === filename);
        return job?.status;
      },
      { timeout: 45000 },
    )
    .toBe("succeeded");
  await page
    .getByRole("button", { name: `Удалить документ ${filename}`, exact: true })
    .click();
  const deleteJob = page.waitForResponse(
    (response) =>
      response.request().method() === "DELETE" &&
      response.url().endsWith(`/jobs/${job.id}`),
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Удалить", exact: true })
    .click();
  expect((await deleteJob).status()).toBe(200);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", {
      name: `Удалить документ ${filename}`,
      exact: true,
    }),
  ).toHaveCount(0);
  expect(
    (await (await page.request.get("/api/runbooks")).json()).items.some(
      (book: any) => book.title === title,
    ),
  ).toBe(false);
});

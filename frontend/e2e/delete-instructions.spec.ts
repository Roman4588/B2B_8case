import { test, expect } from "@playwright/test";

test("deleting an import requires confirmation and refreshes the library", async ({
  page,
}) => {
  let removed = false;
  let deleteCalls = 0;
  await page.route("**/api/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    if (route.request().method() === "DELETE") {
      deleteCalls++;
      removed = true;
      return route.fulfill({ json: { deleted_instructions: 1 } });
    }
    let body: unknown = {};
    if (p === "/api/auth/me")
      body = {
        id: "admin",
        name: "Admin",
        role: "admin",
        email: "test@example.org",
      };
    if (p === "/api/jobs")
      body = removed
        ? []
        : [
            {
              id: "import-1",
              filename: "wrong.json",
              status: "succeeded",
              progress: 1,
              total: 1,
            },
          ];
    if (p === "/api/runbooks")
      body = {
        items: removed
          ? []
          : [
              {
                id: "book-1",
                title: "Wrong guide",
                condition: "Wrong input",
                steps: ["Check"],
                source: "wrong.json",
                status: "ready",
                category: "application",
              },
            ],
      };
    if (p === "/api/incidents") body = { items: [], total: 0 };
    if (p === "/api/summary") body = {};
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "База знаний" })
    .click();
  await page
    .getByRole("button", { name: "Удалить документ wrong.json", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("все инструкции");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Отмена", exact: true })
    .click();
  expect(deleteCalls).toBe(0);
  await page
    .getByRole("button", { name: "Удалить документ wrong.json", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Удалить", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Wrong guide", exact: true }),
  ).toHaveCount(0);
  expect(deleteCalls).toBe(1);
});

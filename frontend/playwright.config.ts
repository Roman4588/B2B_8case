import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:8080",
    trace: "retain-on-failure",
  },
  reporter: "list",
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});

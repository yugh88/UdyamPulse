import { defineConfig, devices } from "@playwright/test";

// The E2E stack runs on its own ports and its own database so it never touches a running demo.
const API_PORT = 8010;
const WEB_PORT = 5183;
const DB = "sqlite:///var/e2e.db";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: `http://127.0.0.1:${WEB_PORT}`, trace: "retain-on-failure", ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
  webServer: [
    {
      command: `cd .. && UP_DB_URL=${DB} .venv/bin/python -m api.seed && UP_DB_URL=${DB} .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `VITE_API_PROXY=http://127.0.0.1:${API_PORT} npx vite --port ${WEB_PORT} --strictPort --host 127.0.0.1`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

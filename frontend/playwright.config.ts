import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.FRONTEND_PORT ?? 3030);
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const HEADED = !!process.env.PWDEBUG || process.env.PW_HEADED === "1";

// Reuse an existing dev server if one is already running on PORT;
// otherwise start one for the test run.
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: BASE_URL,
    headless: !HEADED,
    trace: process.env.CI ? "on-first-retry" : "retain-on-failure",
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `PORT=${PORT} NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL} npm run dev -- -p ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 60_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});

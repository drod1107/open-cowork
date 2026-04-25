import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config. Drives a real Chromium against the real FastAPI
 * backend.
 *
 * The webServer block boots the OpenCowork server before the suite runs.
 * It assumes:
 *   - the backend venv is at ../.venv (created by ./install.sh)
 *   - the frontend has been built (run `npm run build` first)
 *
 * Run: cd frontend && npm run build && npm run e2e
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "list" : "list",
  use: {
    baseURL: process.env.OPENCOWORK_URL || "http://127.0.0.1:7337",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.OPENCOWORK_URL
    ? undefined
    : {
        // Start the FastAPI server. Tests can override via OPENCOWORK_URL.
        command:
          "cd .. && .venv/bin/python -m backend.main",
        url: "http://127.0.0.1:7337/api/health",
        reuseExistingServer: !process.env.CI,
        timeout: 30_000,
        env: { OPENCOWORK_HOST: "127.0.0.1", OPENCOWORK_PORT: "7337" },
      },
});

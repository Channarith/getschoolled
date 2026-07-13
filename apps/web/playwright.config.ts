import { defineConfig, devices } from "@playwright/test";

/**
 * Corporate-demo E2E suite. Runs against the REAL stack (demo fidelity):
 *   make up-e2e      # compose stack with deterministic demo env
 *   npm run e2e      # this suite
 *
 * globalSetup fails fast (with instructions) if the stack is not up, and
 * signs in once as the seeded QA learner, reusing the session via
 * storageState in the specs that need auth.
 */
export const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:3000";
export const AUTH_STATE = "e2e/.auth/learner.json";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: 1,
  reporter: [["line"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      // Investor-demo responsive sanity: a narrow phone viewport.
      // Chromium-based profile — only chromium is installed (npx playwright
      // install chromium); iPhone profiles would demand webkit.
      name: "mobile-viewport",
      testMatch: /i18n-responsive\.spec\.ts/,
      use: { ...devices["Pixel 7"] },
    },
  ],
});

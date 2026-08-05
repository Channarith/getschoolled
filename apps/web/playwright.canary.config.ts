/**
 * Playwright config for the CI regression canary.
 *
 * Runs e2e/canary/source-checks.spec.ts — pure Node.js execSync tests that
 * read source files and assert critical patterns. No browser navigation, no
 * server, no auth needed. Completes in ~5 s on a bare CI runner.
 *
 * Usage:
 *   npx playwright test --config playwright.canary.config.ts
 *
 * Intentional differences from playwright.config.ts:
 *   - No globalSetup (no stack health check, no auth sign-in)
 *   - testDir scoped to e2e/canary only
 *   - Single worker (tests are pure sync, parallelism doesn't help)
 *   - No retries (source checks are deterministic — flake means a real bug)
 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/canary",
  // No globalSetup — these tests need no server, no auth state.
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: [["line"]],
  use: {
    // No baseURL, no storageState — source-level checks only.
  },
  projects: [
    {
      name: "canary",
      use: {},
    },
  ],
});

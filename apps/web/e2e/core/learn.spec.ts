import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";
import { sweepRouteOverflow } from "../lib/overflow";

/**
 * Core P0 — the unlocked classroom (V&V master plan WV-05).
 *
 * Distinct render state from the corporate locked player (covered by
 * e2e/corporate/learn.spec.ts): /class shows the lesson-picker "Start a
 * session" card and manual start, whereas /corporate/learn auto-starts locked.
 */

test.use({ storageState: AUTH_STATE });

test.describe("classroom /class (WV-05) — signed in", () => {
  test("renders Live Class with the start-a-session picker", async ({ page }) => {
    await page.goto("/class");
    await expect(page.getByRole("heading", { name: "Live Class", level: 1 })).toBeVisible();
    // The unlocked classroom exposes a lesson picker before any session starts.
    await expect(page.getByRole("heading", { name: "Start a session" })).toBeVisible();
  });

  test("no horizontal overflow across phone/laptop/desktop", async ({ page }) => {
    await sweepRouteOverflow(page, "/class", { waitFor: "h1" });
  });
});

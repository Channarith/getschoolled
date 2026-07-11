import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";
import { sweepRouteOverflow } from "../lib/overflow";

/**
 * Core P0 — authentication surfaces (V&V master plan WV-03/WV-04).
 *
 * The login page and onboarding wizard are the first thing a new learner sees
 * and were entirely uncovered (the corporate demo suite skips auth). These
 * assert structure + the responsive overflow sweep, not exact copy, so they
 * hold across the 27 locales.
 */

test.describe("login (WV-03) — signed out", () => {
  test("renders the sign-in form and toggles to signup mode", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Sign in", level: 1 })).toBeVisible();
    // Email + password inputs are the stable, locale-independent anchors.
    await expect(page.getByLabel(/Email/i)).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();

    // Switch to account-creation mode — the h1 flips to the signup title.
    await page.getByRole("button", { name: /create.*account|sign up/i }).first().click();
    await expect(page.getByRole("heading", { name: "Create your account", level: 1 })).toBeVisible();
  });

  test("no horizontal overflow across phone/laptop/desktop", async ({ page }) => {
    await sweepRouteOverflow(page, "/login", { waitFor: "h1" });
  });
});

test.describe("onboarding (WV-04) — signed in", () => {
  test.use({ storageState: AUTH_STATE });

  test("wizard opens on the welcome step", async ({ page }) => {
    await page.goto("/onboarding");
    await expect(page.getByRole("heading", { name: "Welcome to Salareen", level: 1 })).toBeVisible();
    // Step 1 of the wizard is the "about you" card.
    await expect(page.getByRole("heading", { name: "Tell us about you" })).toBeVisible();
  });

  test("no horizontal overflow across phone/laptop/desktop", async ({ page }) => {
    await sweepRouteOverflow(page, "/onboarding", { waitFor: "h1" });
  });
});

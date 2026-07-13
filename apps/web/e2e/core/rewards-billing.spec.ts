import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";
import { sweepRouteOverflow } from "../lib/overflow";

/**
 * Core P0 — money/loyalty surfaces (V&V master plan WV-08/WV-10).
 * Rewards catalog + points balance, and the billing plan picker.
 */

test.use({ storageState: AUTH_STATE });

test.describe("rewards (WV-08) — signed in", () => {
  test("shows the points balance and redeem catalog", async ({ page }) => {
    await page.goto("/rewards");
    await expect(page.getByRole("heading", { name: "Rewards", level: 1 })).toBeVisible();
    // Signed in: the balance card renders (not the "please sign in" prompt).
    await expect(page.getByText(/\d+ points/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Redeem" })).toBeVisible();
  });

  test("no horizontal overflow across phone/laptop/desktop", async ({ page }) => {
    await sweepRouteOverflow(page, "/rewards", { waitFor: "h1" });
  });
});

test.describe("billing (WV-10) — signed in", () => {
  test("renders the plan picker", async ({ page }) => {
    await page.goto("/billing");
    await expect(page.getByRole("heading", { name: "Membership & billing", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Choose your plan" })).toBeVisible();
  });

  test("no horizontal overflow across phone/laptop/desktop", async ({ page }) => {
    await sweepRouteOverflow(page, "/billing", { waitFor: "h1" });
  });
});

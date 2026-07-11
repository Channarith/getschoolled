import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";

/**
 * Core P0 — graceful backend-failure UI (V&V master plan WV-18).
 *
 * When the catalog feed fails, the signed-in home must show an explicit error
 * card (`home.error` + friendly detail), not a blank page or a permanent
 * spinner. We force the failure deterministically by aborting the curriculum
 * `/home` request at the network layer.
 */

test.use({ storageState: AUTH_STATE });

test.describe("backend-failure states (WV-18)", () => {
  test("home shows the catalog error card when the feed fails", async ({ page }) => {
    // getHomeFeed() calls `${CURRICULUM_URL}/home?...`; match both same-origin
    // (`/curriculum/home?`) and direct (`:8005/home?`) routings.
    await page.route(/\/home\?/, (route) => route.abort());

    await page.goto("/");
    await expect(page.getByText("Could not load the catalog:")).toBeVisible({ timeout: 20_000 });
    // It must not get stuck on the loading affordance.
    await expect(page.getByText("Loading your catalog…")).toBeHidden();
  });
});

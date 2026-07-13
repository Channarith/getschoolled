import { expect, test } from "@playwright/test";

/**
 * Regression — /auth/me 401 handling.
 *
 * Two bugs surfaced as `GET /identity/auth/me 401 (Unauthorized)` spam on the
 * deployed site:
 *  1. Signed-out visitors still fired getMe() on load / nav clicks — a request
 *     guaranteed to 401. getMe() now short-circuits when there is no token, so
 *     NO /auth/me request is made while signed out.
 *  2. A stale/expired token (e.g. after a redeploy rotated the auth signing key)
 *     was kept forever, so every click re-fired failing authed requests.
 *     jsonOrThrow() now clears the token on any 401, returning the UI to a clean
 *     signed-out state.
 *
 * These run signed-out (no storageState).
 */

test.describe("auth/me 401 handling", () => {
  test("signed-out load makes no /auth/me request", async ({ page }) => {
    const authMe: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/auth/me")) authMe.push(r.url());
    });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // FlagsProvider (in the layout) resolves without hitting /auth/me when signed out.
    expect(authMe).toHaveLength(0);
    // Confirm we really are signed out (no token planted).
    const token = await page.evaluate(() => localStorage.getItem("aoep_token"));
    expect(token).toBeNull();
  });

  test("a stale/expired token is cleared after a 401", async ({ page }) => {
    // Plant a bogus token before app JS runs; the first authed call (getMe from
    // the FlagsProvider) will 401 and the client must drop it.
    await page.addInitScript(() => {
      localStorage.setItem("aoep_token", "bogus.invalid.token");
    });
    let saw401 = false;
    page.on("response", (res) => {
      if (res.url().includes("/auth/me") && res.status() === 401) saw401 = true;
    });
    await page.goto("/");
    // The bad token is rejected and removed, returning to signed-out state.
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("aoep_token")), { timeout: 15_000 })
      .toBeNull();
    expect(saw401).toBe(true);
  });
});

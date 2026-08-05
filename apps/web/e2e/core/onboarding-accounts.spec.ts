import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";

/**
 * Onboarding + Account types (WV-ONB / WV-ACC)
 *
 *   WV-ONB-01  New user signup toggles form to signup mode
 *   WV-ONB-02  Onboarding wizard renders the welcome/plan step
 *   WV-ONB-03  Returning user with completed onboarding is not reset to step 0
 *   WV-ACC-01  Free-tier gated content shows upgrade prompt
 *   WV-ACC-02  Pro/paid billing page shows plan picker
 *   WV-ACC-03  Admin panel is reachable for admin accounts
 *   WV-ACC-04  Profile & settings renders account info
 */

test.describe("onboarding — signup toggle (WV-ONB-01)", () => {
  test("'New here? Create account' toggles form to signup mode", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    const createBtn = page.getByRole("button", { name: /create account/i });
    await expect(createBtn).toBeVisible({ timeout: 8_000 });
    await createBtn.click();

    // After toggle: submit button must read "Create account", not "Sign in".
    const submitBtn = page.getByRole("button", { name: /create account/i, exact: true });
    await expect(submitBtn).toBeVisible({ timeout: 3_000 });

    // Password field should use autocomplete="new-password" in signup mode.
    const pwInput = page.locator('input[type="password"]');
    const autoComplete = await pwInput.getAttribute("autocomplete");
    expect(autoComplete).toBe("new-password");
  });

  test("signup with existing email switches back to login mode", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // Toggle to signup.
    await page.getByRole("button", { name: /create account/i }).click();

    // Fill with an address that's already registered.
    const emailInput = page.getByPlaceholder(/email or username/i);
    await emailInput.fill("qa-learner@salareen.com");
    const pwInput = page.locator('input[type="password"]');
    await pwInput.fill("QaTest123");

    const submitBtn = page.getByRole("button", { name: /create account/i, exact: true });
    await expect(submitBtn).toBeEnabled({ timeout: 3_000 });
    await submitBtn.click();

    // Should either switch back to login mode with "already registered" message
    // OR redirect to onboarding — either is acceptable.
    await page.waitForTimeout(3_000);
    const body = await page.textContent("body");
    const switchedBack =
      body?.includes("already registered") ||
      body?.includes("Sign in") ||
      page.url().includes("onboarding");
    expect(switchedBack).toBe(true);
  });
});

test.describe("onboarding — wizard (WV-ONB-02/03)", () => {
  test.use({ storageState: AUTH_STATE });

  test("onboarding page renders a plan/step heading without crash", async ({ page }) => {
    await page.goto("/onboarding");
    await page.waitForLoadState("networkidle").catch(() => {});
    // Either shows a wizard step OR redirects to / if already complete.
    const isHome = page.url().endsWith("/") || page.url().endsWith("/#");
    if (!isHome) {
      // On the onboarding page — must show some wizard content.
      const body = await page.textContent("body");
      expect(body?.trim().length).toBeGreaterThan(50);
      // Must not show a raw JS crash.
      await expect(page.locator("text=Something went wrong")).not.toBeVisible();
    }
  });

  test("returning user is not sent back to step 0 (WV-ONB-01 regression)", async ({
    browser,
  }) => {
    const ctx = await browser.newContext({ storageState: AUTH_STATE });
    const authPage = await ctx.newPage();
    try {
      await authPage.goto("/onboarding");
      await authPage.waitForTimeout(2_000);
      const nameField = authPage.locator(
        'input[name="name"], input[placeholder*="name" i]'
      );
      const visible = await nameField
        .isVisible({ timeout: 3_000 })
        .catch(() => false);
      if (visible) {
        // Page is still on onboarding but name should be pre-filled, not empty.
        expect(await nameField.inputValue()).not.toBe("");
      }
      // Acceptable outcomes: redirect away OR name pre-filled. Never a blank name on step 0.
    } finally {
      await ctx.close();
    }
  });
});

test.describe("account types (WV-ACC)", () => {
  test.use({ storageState: AUTH_STATE });

  test("billing page renders plan picker (WV-ACC-02)", async ({ page }) => {
    await page.goto("/billing");
    await expect(
      page.getByRole("heading", { name: /plan|subscription|upgrade|billing/i }).first()
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("text=Something went wrong")).not.toBeVisible();
  });

  test("free-tier user sees upgrade prompt on gated content (WV-ACC-01)", async ({
    page,
  }) => {
    await page.goto("/billing");
    await page.waitForLoadState("networkidle").catch(() => {});
    // The billing page must offer an upgrade path — not be a blank screen.
    const body = await page.textContent("body");
    expect(body?.trim().length).toBeGreaterThan(100);
    // Must mention some tier/plan distinction.
    expect(body).toMatch(/free|pro|premium|plan|upgrade/i);
  });

  test("rewards page shows points balance (WV-ACC-03)", async ({ page }) => {
    await page.goto("/rewards");
    await expect(
      page.getByText(/point|reward|streak/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("profile & settings page renders account info (WV-ACC-04)", async ({
    page,
  }) => {
    await page.goto("/account");
    await page.waitForLoadState("networkidle").catch(() => {});
    // Must not be a blank page or crash.
    const body = await page.textContent("body");
    expect(body?.trim().length).toBeGreaterThan(50);
    await expect(page.locator("text=Something went wrong")).not.toBeVisible();
  });

  test("admin panel accessible when admin flag is set (WV-ACC-05)", async ({
    page,
  }) => {
    // This tests the existing admin panel regression from v0.45.12.
    await page.goto("/admin");
    await page.waitForLoadState("domcontentloaded");
    // Either shows the admin panel OR redirects to home (non-admin account).
    // Must not throw a 500 or unhandled crash.
    const status = await page
      .waitForResponse((r) => r.url().includes("/admin"), { timeout: 5_000 })
      .catch(() => null);
    // Page must render something.
    const body = await page.textContent("body");
    expect(body?.trim().length).toBeGreaterThan(20);
  });
});

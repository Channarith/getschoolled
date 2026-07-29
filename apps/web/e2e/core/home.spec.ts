import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";
import { sweepRouteOverflow } from "../lib/overflow";

/**
 * Core P0 — home / landing (V&V master plan WV-01/WV-02).
 * Signed-out marketing landing (email capture) and the signed-in catalog rails.
 */

test.describe("landing (WV-01) — signed out", () => {
  test("marketing hero with email capture and a sign-in path", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1").first()).toBeVisible();
    // Email-capture form: the email/username input and the sign-in affordance are
    // the locale-independent anchors of the logged-out hero. The input uses
    // type="text" with an email/username placeholder (autocomplete=username).
    await expect(page.locator('input[autocomplete="username"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in/i }).first()).toBeVisible();
  });

  test("no horizontal overflow across phone/laptop/desktop", async ({ page }) => {
    await sweepRouteOverflow(page, "/", { waitFor: "h1" });
  });
});

test.describe("home catalog (WV-02) — signed in", () => {
  test.use({ storageState: AUTH_STATE });

  test("renders the catalog without a stuck spinner or crash", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && !/status of 401/.test(msg.text())) errors.push(msg.text());
    });
    await page.goto("/");
    await expect(page.locator("h1").first()).toBeVisible();
    // The feed resolves to rails or an explicit empty state — never a
    // permanent loading spinner (the loading copy must disappear).
    await expect(page.getByText("Loading your catalog…")).toBeHidden({ timeout: 20_000 });
    await expect(page.getByText("Could not load the catalog:")).toHaveCount(0);
    expect(errors, `console errors: ${errors.join(" | ")}`).toHaveLength(0);
  });

  test("no horizontal overflow across phone/laptop/desktop", async ({ page }) => {
    await sweepRouteOverflow(page, "/", { waitFor: "h1" });
  });
});

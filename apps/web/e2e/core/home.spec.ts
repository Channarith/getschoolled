import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";
import { sweepRouteOverflow } from "../lib/overflow";

/**
 * Core P0 — home / landing (V&V master plan WV-01/WV-02).
 * Signed-out landing (logo, demo, and login) and the signed-in catalog rails.
 */

test.describe("landing (WV-01) — signed out", () => {
  test("logo landing offers the demo and login", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("img", { name: /salareen mascot/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /try the demo/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /^log in$/i })).toBeVisible();
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

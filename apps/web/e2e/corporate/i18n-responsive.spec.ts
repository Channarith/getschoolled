import { expect, test } from "@playwright/test";

/**
 * CD-E5 — i18n + responsive sanity for the demo surfaces.
 * Runs in both the desktop `chromium` project and the `mobile-viewport`
 * project (iPhone 12) — see playwright.config.ts.
 */

test.describe("i18n (CD-E5)", () => {
  test("Spanish locale translates the corporate page (no raw keys)", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("aiclassroom.locale.v1", "es");
    });
    await page.goto("/corporate");
    await expect(
      page.getByRole("heading", { name: "Formación corporativa" }),
    ).toBeVisible();
    await expect(page.getByText(/corporate\.[a-zA-Z]+/)).toHaveCount(0);
  });
});

test.describe("responsive sanity (CD-E5)", () => {
  for (const route of ["/corporate", "/jobs"]) {
    test(`${route} has no horizontal overflow and visible CTAs`, async ({ page }) => {
      await page.goto(route);
      await expect(page.locator("h1")).toBeVisible();
      // No horizontal scrollbar: content must fit the viewport width.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${route} overflows horizontally by ${overflow}px`).toBeLessThanOrEqual(1);
      // The page's primary interactive element is on screen.
      await expect(page.locator("button").first()).toBeVisible();
    });
  }
});

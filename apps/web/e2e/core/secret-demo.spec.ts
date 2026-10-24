import { expect, test } from "@playwright/test";

/** The On the Go demo is not advertised; four quick clicks on the logo open it. */

test.describe("hidden On the Go demo (signed out)", () => {
  test("the demo hub does not list On the Go", async ({ page }) => {
    await page.goto("/demo");
    await expect(page.getByRole("link", { name: /drivers?[’']? ?ed|driver/i }).first()).toBeVisible();
    await expect(page.locator("body")).not.toContainText(/on[- ]the[- ]go/i);
    if (process.env.DEMO_HUB_SHOT) await page.screenshot({ path: process.env.DEMO_HUB_SHOT, fullPage: true });
    await expect(page.locator('a[href="/demo/on-the-go"]')).toHaveCount(0);
  });

  test("four quick clicks on the logo open the audio demo", async ({ page }) => {
    await page.goto("/demo");
    const logo = page.locator("a.brand, .dn-anon-brand, [data-secret-logo]").first();
    await expect(logo).toBeVisible();
    for (let i = 0; i < 4; i += 1) await logo.click({ noWaitAfter: true, delay: 20 });
    await expect(page).toHaveURL(/\/demo\/on-the-go$/);
  });

  test("a single logo click still goes home", async ({ page }) => {
    await page.goto("/our-story");
    await page.locator("a.brand").first().click();
    await expect(page).toHaveURL(/\/$/);
  });
});

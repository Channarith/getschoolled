import { expect, test } from "@playwright/test";

import { sweepRouteOverflow } from "../lib/overflow";

/**
 * Horizontal overflow sweep for high-traffic routes (responsive audit §3).
 * Public routes only — no auth storage required.
 */
const PUBLIC_OVERFLOW_ROUTES: { path: string; waitFor?: string }[] = [
  { path: "/login", waitFor: "h1" },
  { path: "/onboarding", waitFor: "h1, .aoep-immersive-setup" },
  { path: "/browse", waitFor: "h1, h2" },
  { path: "/group-classes", waitFor: "h1" },
  { path: "/homework", waitFor: "h1, h2" },
  { path: "/training", waitFor: "h1, h2" },
  { path: "/security", waitFor: "h1, h2" },
  { path: "/billing", waitFor: "h1, h2" },
  { path: "/class", waitFor: "h1, h2" },
];

for (const route of PUBLIC_OVERFLOW_ROUTES) {
  test(`${route.path} has no horizontal overflow across sweep viewports`, async ({ page }) => {
    await sweepRouteOverflow(page, route.path, { waitFor: route.waitFor });
  });
}

test("onboarding uses immersive shell without global header on phone", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/onboarding");
  await expect(page.locator(".aoep-immersive-setup")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".site-header")).toHaveCount(0);
  await expect(page.locator(".site-footer")).toHaveCount(0);
});

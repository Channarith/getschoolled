import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";

/**
 * CD-E3 — course completion: finishing a corporate course records the
 * enrollment as passed and surfaces reward points. Assertions are
 * delta/state-tolerant so re-runs against the same seeded QA account
 * pass (first pass earns points; later passes show the balance).
 */

const LESSON_ID = "ai-powered-productivity";

test.use({ storageState: AUTH_STATE });

test("finishing a corporate course completes it and shows reward points (CD-E3)", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "speechSynthesis", {
      value: {
        speak: () => {}, cancel: () => {}, pause: () => {}, resume: () => {},
        getVoices: () => [], speaking: false, pending: false, paused: false,
        onvoiceschanged: null, addEventListener: () => {},
        removeEventListener: () => {}, dispatchEvent: () => true,
      },
    });
  });
  await page.goto(`/corporate/learn?lesson=${LESSON_ID}`);
  await expect(page.getByText(/Slide 1 of \d+/)).toBeVisible();

  // See a little content first (mirrors the demo), then finish.
  await page.getByRole("button", { name: "Next slide →" }).click();
  await expect(page.getByText(/Slide 2 of \d+/)).toBeVisible();
  await page.getByRole("button", { name: "Finish class", exact: true }).click();

  // A post-class survey may be enabled; completing/skipping it must not be
  // required to see the completion banner — but if the survey card shows
  // first, the finish banner appears alongside/after it. Wait for either
  // completion variant:
  //   first run:  "🎉 Course complete — you earned N reward points!"
  //   re-runs:    "✅ Course complete!" + reward balance
  const banner = page.getByText(/Course complete/);
  await expect(banner.first()).toBeVisible({ timeout: 30_000 });

  // Points are visible in both variants (earned or balance) with a rewards link.
  await expect(page.getByText(/reward points|points ·|Reward balance/i).first()).toBeVisible();
  await expect(page.locator('a[href="/rewards"]').first()).toBeVisible();

  // Locked-mode completion offers the corporate follow-ups.
  await expect(page.getByRole("button", { name: /Take it again|again/i })).toBeVisible();
});

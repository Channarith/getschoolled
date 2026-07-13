import { expect, test } from "@playwright/test";

/**
 * CD-E1 — /corporate catalog: the investor-demo landing view.
 * Anonymous (catalog browsing requires no login).
 */

// The 11 sample-curriculum lessons tagged AUDIENCE: corporate (pinned by
// services/orchestrator/tests/test_corporate_lessons.py).
const CORPORATE_COURSE_TITLES = [
  "AI Fluency: Essentials for the Modern Workplace",
  "AI-Powered Productivity",
  "AI Solutions Builder",
  "AI and Machine Learning Fellowship",
  "AI Transformation Architect",
  "Applied Data Engineering",
  "Data & Insights for Business Decisions",
  "Data Fellowship",
  "AI Product Engineering",
  "DevOps Engineering Upskiller",
  "Java Software Engineering",
];

// Seeded by services/curriculum/src/curriculum/corporate_programs.py.
const SEEDED_PROGRAM_TITLES = [
  "AI Fluency for Teams",
  "AI Engineering Upskilling",
  "Data & Decisions",
  "AI Leadership",
];

test.describe("corporate catalog (CD-E1)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/corporate");
  });

  test("renders all 11 AI-led corporate courses with start buttons", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "AI-led courses" })).toBeVisible();
    for (const title of CORPORATE_COURSE_TITLES) {
      await expect(page.getByRole("heading", { name: title })).toBeVisible();
    }
    const startButtons = page.getByRole("button", { name: "Start course" });
    await expect(startButtons.nth(10)).toBeVisible();
    expect(await startButtons.count()).toBeGreaterThanOrEqual(11);
  });

  test("groups courses into AI, Data, and Engineering tracks", async ({ page }) => {
    for (const track of ["Artificial Intelligence", "Data", "Engineering"]) {
      await expect(
        page.getByRole("heading", { name: new RegExp(`^${track} programmes`) }),
      ).toBeVisible();
    }
  });

  test("programs section shows the seeded corporate tracks (blocker-1 regression trap)", async ({ page }) => {
    // The empty state must NOT appear once startup seeding is in place.
    await expect(page.getByText("No corporate programs yet")).toHaveCount(0);
    for (const title of SEEDED_PROGRAM_TITLES) {
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    }
    // Program course entries deep-link into the locked corporate player.
    const programCourseLinks = page.locator('a[href^="/corporate/learn?lesson="]');
    expect(await programCourseLinks.count()).toBeGreaterThanOrEqual(11);
  });

  test("team-seats CTA is a contact affordance, not a dead end (blocker-2 regression trap)", async ({ page }) => {
    const cta = page.getByRole("button", { name: "Talk to us about team seats" }).first();
    await expect(cta).toBeVisible();
    const href = await cta.locator("xpath=ancestor::a").getAttribute("href");
    expect(href).toContain("mailto:");
    // The old dead end must be gone.
    await expect(page.getByRole("button", { name: "Assign to team" })).toHaveCount(0);
  });

  test("no raw i18n keys or console errors on the catalog page", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      // Anonymous browsing legitimately gets 401s from auth-gated widgets
      // (rewards/flags); real JS errors stay fatal.
      if (msg.type() === "error" && !/status of 401/.test(msg.text())) {
        errors.push(msg.text());
      }
    });
    await page.reload();
    await expect(page.getByRole("heading", { name: "AI-led courses" })).toBeVisible();
    await expect(page.getByText(/corporate\.[a-zA-Z]+/)).toHaveCount(0);
    expect(errors, `console errors: ${errors.join(" | ")}`).toHaveLength(0);
  });
});

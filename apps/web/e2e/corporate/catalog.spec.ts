import { expect, test } from "@playwright/test";

/**
 * CD-E1 — /corporate catalog: the investor-demo landing view.
 * Anonymous (catalog browsing requires no login).
 */

const CORPORATE_COURSE_TITLES = [
  // Compliance & safety
  "Sexual Harassment Prevention Training",
  "Workplace Violence Prevention",
  "Workplace Ethics and Integrity",
  "Anti-Bribery and Corruption",
  "Diversity, Equity, and Inclusion in the Workplace",
  "Social Media at Work",
  "Fire Safety and Prevention",
  "OSHA General Industry Safety",
  "Forklift and Powered Industrial Truck Safety",
  "Food Handler Safety Certification",
  "Lab Safety Fundamentals",
  "Liquid Cooling & Thermal Materials Safety",
  "HIPAA Privacy and Security Training",
  "Data Privacy at Work",
  "Cybersecurity Fundamentals",
  "Security Policies at Work",
  "Security Guard Certification Training",
  "Trade Compliance Essentials",
  "US Export Control Regulations",
  "Automotive Safety Awareness",
  "ASE Automotive Service Excellence Certification",
  // AI / Data / Engineering
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

const SEEDED_PROGRAM_TITLES = [
  "Workplace Safety & OSHA",
  "HR & Workplace Conduct",
  "Privacy, Security & Data Protection",
  "Food Handler Certification",
  "Trade Compliance & Export Control",
  "Automotive Safety & ASE",
  "AI Fluency for Teams",
  "AI Engineering Upskilling",
  "Data & Decisions",
  "AI Leadership",
];

test.describe("corporate catalog (CD-E1)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/corporate");
  });

  test("renders corporate compliance and AI courses with start buttons", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Corporate courses" })).toBeVisible();
    for (const title of CORPORATE_COURSE_TITLES) {
      await expect(page.getByRole("heading", { name: title })).toBeVisible();
    }
    const startButtons = page.getByRole("button", { name: "Start course" });
    expect(await startButtons.count()).toBeGreaterThanOrEqual(CORPORATE_COURSE_TITLES.length);
  });

  test("groups courses into compliance and upskilling tracks", async ({ page }) => {
    for (const track of [
      "Workplace Compliance",
      "Workplace Safety",
      "Privacy & Security",
      "Trade & Export Control",
      "Automotive",
      "Artificial Intelligence",
      "Data",
      "Engineering",
    ]) {
      await expect(
        page.getByRole("heading", { name: new RegExp(`^${track} programmes`) }),
      ).toBeVisible();
    }
  });

  test("programs section shows the seeded corporate tracks (blocker-1 regression trap)", async ({ page }) => {
    await expect(page.getByText("No corporate programs yet")).toHaveCount(0);
    for (const title of SEEDED_PROGRAM_TITLES) {
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    }
    const programCourseLinks = page.locator('a[href^="/corporate/learn?lesson="]');
    expect(await programCourseLinks.count()).toBeGreaterThanOrEqual(CORPORATE_COURSE_TITLES.length);
  });

  test("team-seats CTA is a contact affordance, not a dead end (blocker-2 regression trap)", async ({ page }) => {
    const cta = page.getByRole("button", { name: "Talk to us about team seats" }).first();
    await expect(cta).toBeVisible();
    const href = await cta.locator("xpath=ancestor::a").getAttribute("href");
    expect(href).toContain("mailto:");
    await expect(page.getByRole("button", { name: "Assign to team" })).toHaveCount(0);
  });

  test("no raw i18n keys or console errors on the catalog page", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error"
        && !/status of 401/.test(msg.text())
        // Next.js client-side RSC prefetch failures for other routes are noisy
        // but harmless — they fall back to browser navigation automatically.
        && !/Failed to fetch RSC payload/.test(msg.text())) {
        errors.push(msg.text());
      }
    });
    await page.reload();
    await expect(page.getByRole("heading", { name: "Corporate courses" })).toBeVisible();
    expect(errors).toEqual([]);
  });
});

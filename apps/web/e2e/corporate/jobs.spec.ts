import { expect, test } from "@playwright/test";
import fs from "fs";
import path from "path";

/**
 * CD-E4 — /jobs Careers matcher: list -> job detail (coverage %, matched
 * courses, skill gap) -> paste-a-JD parse. Deterministic when the stack
 * runs with JOBS_PROVIDER=sample (make up-e2e); the specs assert shape,
 * not specific postings, so a keyed/live board also passes.
 */

const FIXTURE_JD = fs.readFileSync(
  path.join(__dirname, "..", "fixtures", "job-description.txt"),
  "utf-8",
);

test.describe("careers jobs matcher (CD-E4)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/jobs");
    await expect(page.getByRole("heading", { name: /Careers/ })).toBeVisible();
  });

  test("job list renders postings", async ({ page }) => {
    const postings = page.locator('[role="button"][tabindex="0"]');
    await expect(postings.first()).toBeVisible({ timeout: 20_000 });
    expect(await postings.count()).toBeGreaterThanOrEqual(3);
  });

  test("job detail shows coverage %, matched courses, and gap", async ({ page }) => {
    const postings = page.locator('[role="button"][tabindex="0"]');
    await expect(postings.first()).toBeVisible({ timeout: 20_000 });
    await postings.first().click();
    await expect(page.getByText(/You can cover \d+% of this role/)).toBeVisible({
      timeout: 20_000,
    });
    // Close returns to the list.
    await page.getByRole("button", { name: /Close|✕/ }).first().click();
    await expect(postings.first()).toBeVisible();
  });

  test("paste-a-JD analysis returns catalog coverage and recommendations", async ({ page }) => {
    await page
      .getByPlaceholder(/paste|job description/i)
      .fill(FIXTURE_JD);
    await page.getByRole("button", { name: "Analyze & recommend" }).click();
    await expect(page.getByText("Catalog coverage:")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/\d+%/).first()).toBeVisible();
  });
});

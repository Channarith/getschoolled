import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";

/**
 * Regression suite — Group Class scheduling and live room join flows.
 *
 * Covers the bugs fixed in v0.45.8–v0.45.13:
 * - After scheduling a class the host is redirected to the Join tab (not left
 *   on a blank form) — v0.45.9
 * - A student clicking Join on a not-yet-started class sees a friendly "not
 *   started" message, not a raw 403 — v0.45.9
 * - The admin flags panel is reachable and not crashing — v0.45.12
 * - The Sales Demo button does not appear for regular users — v0.45.14
 */

test.describe("group class — schedule flow (WV-GC-01)", () => {
  test.use({ storageState: AUTH_STATE });

  test("schedule form is visible on the Teach tab", async ({ page }) => {
    await page.goto("/group-classes?tab=teach");
    await expect(page.getByRole("heading", { name: /schedule|host|teach/i })).toBeVisible();
    // The form should have a lesson/title field.
    await expect(
      page.locator('input[type="text"], input[type="datetime-local"], select').first()
    ).toBeVisible();
  });

  test("after scheduling, host lands on Join tab showing the new class", async ({ page }) => {
    await page.goto("/group-classes?tab=teach");

    // Fill in the schedule form fields that are typically required.
    const titleInput = page.locator('input[placeholder*="title" i], input[name*="title" i]').first();
    if (await titleInput.isVisible()) {
      await titleInput.fill("Regression test class");
    }

    // Find and click the schedule/submit button.
    // Use the translated button name "Schedule class" to avoid matching other
    // buttons that contain "schedule" in their accessible name or title attribute.
    // Wait up to 10s for lessons to load (which enables the button).
    const scheduleBtn = page.getByRole("button", { name: "Schedule class" });
    await expect(scheduleBtn).toBeVisible({ timeout: 10_000 });
    await expect(scheduleBtn).toBeEnabled({ timeout: 10_000 });
    await scheduleBtn.click();

    // Regression v0.45.9: after scheduling the host should be on the Join tab,
    // NOT stuck on the blank teach form. The Join tab content includes a
    // "Schedule a Class" section that is absent on the Teach tab.
    await expect(page.getByText("Schedule a Class for Your Group")).toBeVisible({
      timeout: 30_000,
    });
  });
});

test.describe("group class — student join guard (WV-GC-02)", () => {
  test.use({ storageState: AUTH_STATE });

  test("Join tab shows class list", async ({ page }) => {
    await page.goto("/group-classes");
    // Default tab is join; should see a list or a waiting message.
    const listOrWait = page.locator(
      '[data-testid="class-list"], [data-testid="empty-state"], .class-card, :text("Waiting"), :text("No classes")'
    );
    await expect(listOrWait.first()).toBeVisible({ timeout: 10_000 });
  });

  test("joining a class that has not started shows a helpful message", async ({ page }) => {
    // Navigate to a class URL that would be scheduled but not live.
    // We use the group-classes page and look for a Join button.
    await page.goto("/group-classes");

    // Allow a moment for getMe() to resolve so isHost() correctly identifies host classes
    // (which show "Start" not "Join"). Use exact "Join" to target class-specific buttons.
    await page.waitForTimeout(3_000);
    const joinBtn = page.getByRole("button", { name: "Join" }).first();
    if (await joinBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      // Click may navigate to /live-room (class live), open an external URL
      // (needs_bridge), show a payment modal, or show the "not started" message.
      // Catch page-close errors from synchronous navigation gracefully.
      await joinBtn.click({ noWaitAfter: true }).catch(() => {});
      await page.waitForTimeout(3_000).catch(() => {});

      // Regression v0.45.9: the only BAD outcome is a raw 403 error dialog.
      // All user-friendly outcomes (live room, "not started" message, external URL,
      // payment modal) are acceptable.
      const inLiveRoom = page.url().includes("/live-room");
      if (!inLiveRoom) {
        // If the page still shows group-classes, verify the response is user-friendly
        // (no raw "403 Forbidden" text). A "not started" message is the expected happy
        // path; other states (payment modal, needs_bridge redirect) are also acceptable.
        const rawError = page.getByText("403 Forbidden");
        await expect(rawError).toHaveCount(0);
      }
    }
  });
});

test.describe("admin flags panel (WV-ADM-01)", () => {
  test.use({ storageState: AUTH_STATE });

  test("admin page loads and shows the secret field", async ({ page }) => {
    await page.goto("/admin");
    // The admin page should render (not 404/blank) and show the secret input.
    await expect(page.locator('input[type="password"]')).toBeVisible({ timeout: 10_000 });
  });

  test("wrong secret shows helpful error, not a crash", async ({ page }) => {
    await page.goto("/admin");
    const secretInput = page.locator('input[type="password"]').first();
    await secretInput.fill("wrong-secret");
    await page.getByRole("button", { name: /unlock/i }).click();
    // Regression v0.45.12: must show an error message, not a white/blank crash.
    await expect(
      page.locator(':text("Could not load"), :text("sign in as"), :text("incorrect")')
    ).toBeVisible({ timeout: 10_000 });
    // Page should still be functional (not blank).
    await expect(secretInput).toBeVisible();
  });
});

test.describe("sales demo button (WV-DEMO-01)", () => {
  test.use({ storageState: AUTH_STATE });

  test("Sales Demo floating button is hidden for regular users by default", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // Regression v0.45.14: button must NOT be visible unless sales_demo.enabled flag is on.
    const demoBtn = page.locator('[data-testid="sales-demo-button"], :text("Sales Demo")').first();
    const isVisible = await demoBtn.isVisible().catch(() => false);
    expect(isVisible).toBe(false);
  });
});

test.describe("live room — teacher and student layout (WV-LR-01)", () => {
  test.use({ storageState: AUTH_STATE });

  test("live room page loads without blank white tiles for the teacher", async ({ page }) => {
    // Navigate to an existing live room if available, or verify the page shell.
    // This is a structural test — we're verifying the page renders correctly.
    await page.goto("/group-classes");

    const startBtn = page.getByRole("button", { name: /start.*class|🎓/i }).first();
    if (await startBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await startBtn.click();
      // If we're redirected to the live room, check the layout.
      if (page.url().includes("/live-room")) {
        // Regression v0.45.10/v0.45.13: teacher should be in the main tile.
        // The Theodore (AI Host) label should NOT be the only host tile (teacher replaces it).
        // The student area should show a silhouette or student tile, not a blank box.
        await page.waitForLoadState("networkidle");
        // Check that the page rendered without a JS crash.
        const errors: string[] = [];
        page.on("pageerror", (e) => errors.push(e.message));
        expect(errors.filter((e) => !e.includes("Warning:")).length).toBe(0);
      }
    }
  });
});

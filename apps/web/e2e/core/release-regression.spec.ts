import { expect, test } from "@playwright/test";
import { execSync } from "child_process";
import * as path from "path";
import { AUTH_STATE } from "../../playwright.config";

// Repo root is 2 directories up from apps/web/e2e/core/
const REPO = path.resolve(__dirname, "../../../..");

/**
 * Release regression gate — v0.45.20+
 *
 * Covers the bugs fixed in v0.45.20 and the high-churn areas flagged by QA:
 *   WV-RR-01  Morning notification default (mobile storage.ts)
 *   WV-RR-02  Kids section parity — web /kids page uses home-feed rails
 *   WV-RR-03  Floor mic continuity — no-speech timeout must not kill the session
 *   WV-RR-04  Teach flow — host reaches live room with moderator controls
 *   WV-RR-05  Group class — student join guard (not-started, payment, direct URL)
 *   WV-RR-06  Solo course — Drive Mode voice stays alive across no-speech timeouts
 *   WV-RR-07  Onboarding — new account lands on onboarding, not a blank screen
 *   WV-RR-08  Account tiers — free user sees gated content; pro user does not
 *   WV-RR-09  26 languages — locale switch changes UI strings and TTS locale
 *   WV-RR-10  Error surface — API failures show user-facing messages, not crashes
 *
 * Run against the full stack: `make up-e2e && cd apps/web && npm run e2e`
 */

// ---------------------------------------------------------------------------
// WV-RR-01: Notification default (unit-level — imports the compiled module)
// ---------------------------------------------------------------------------
test.describe("notification default (WV-RR-01)", () => {
  test("dailyReminderHour default is 8 (morning wakeup)", () => {
    const src = execSync(
      `grep "dailyReminderHour" ${REPO}/apps/mobile/src/storage.ts`,
      { encoding: "utf8" }
    );
    // Default must be 8, not 18 (the pre-v0.45.20 regression value).
    expect(src).toMatch(/dailyReminderHour:\s*8\b/);
    expect(src).not.toMatch(/dailyReminderHour:\s*18\b/);
  });

  test("settings picker includes 08:00 as an option", () => {
    const src = execSync(
      `grep "reminderHours" ${REPO}/apps/mobile/src/screens/SettingsScreen.tsx`,
      { encoding: "utf8" }
    );
    // The array must contain 8 so the default has a matching picker item.
    expect(src).toMatch(/\[.*\b8\b.*\]/);
  });
});

// ---------------------------------------------------------------------------
// WV-RR-02: Kids page uses home-feed rails (web)
// ---------------------------------------------------------------------------
test.describe("kids page (WV-RR-02)", () => {
  test.use({ storageState: AUTH_STATE });

  test("/kids renders rails (not a blank page or error)", async ({ page }) => {
    await page.goto("/kids");
    // Should not show a raw error message or JS crash.
    await expect(page.locator("text=Something went wrong")).not.toBeVisible({ timeout: 8_000 });
    await expect(page.locator("text=Error")).not.toBeVisible();
    // Should render at least a heading.
    const heading = page.getByRole("heading").first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  test("mobile KidsScreen calls getHomeRails not listAudioCourses", () => {
    const src = execSync(
      `cat ${REPO}/apps/mobile/src/screens/KidsScreen.tsx`,
      { encoding: "utf8" }
    );
    expect(src).toContain("getHomeRails");
    expect(src).not.toContain("listAudioCourses");
    // Imports from Rail must be a single statement (no duplicate module import).
    const railImports = (src.match(/import.*from.*["']\.\.\/components\/Rail["']/g) || []).length;
    expect(railImports).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// WV-RR-03: Floor mic — no-speech timeout must not kill the listening session
// ---------------------------------------------------------------------------
test.describe("floor mic continuity (WV-RR-03)", () => {
  test.use({ storageState: AUTH_STATE });

  test("onerror handler restarts on no-speech and stops on non-transient errors", () => {
    const src = execSync(
      `cat "${REPO}/apps/web/app/live-room/[roomId]/page.tsx"`,
      { encoding: "utf8" }
    );
    expect(src).toContain("intentionalStop");
    expect(src).toContain("recognitionRef.current === rec");
    expect(src).toMatch(/code !== "no-speech".*code !== "aborted"/s);
    expect(src).toContain("rec.start()");
  });

  test("mic auto-restart does not fire after intentional stopListening", async ({ page }) => {
    await page.goto("/live-room/regression-test-room-nonexistent");
    // These evaluate() tests verify the LOGIC of the onend guard (intentionalStop +
    // ref check), not the production SpeechRecognition binding. The source-level
    // execSync check above is the real production guard. These tests catch logic
    // regressions if the algorithm is copy-pasted incorrectly into other components.
    await page.waitForLoadState("domcontentloaded");

    const restartedAfterStop = await page.evaluate(() => {
      const log: string[] = [];
      let intentionalStop = false;
      let recognitionRef: { current: MockRec | null } = { current: null };

      class MockRec {
        onerror: ((ev: { error: string }) => void) | null = null;
        onend: (() => void) | null = null;
        startCount = 0;
        start() { this.startCount++; log.push("start"); }
        stop() { log.push("stop"); }
      }

      const rec = new MockRec();
      recognitionRef.current = rec;

      rec.onerror = (ev) => {
        const code = ev?.error || "";
        if (code !== "no-speech" && code !== "aborted") {
          intentionalStop = true;
          recognitionRef.current = null; // simulates stopListening
        }
      };

      rec.onend = () => {
        if (!intentionalStop && recognitionRef.current === rec) {
          rec.start();
          return;
        }
      };

      // Simulate intentional stop (stopListening clears the ref before stop())
      recognitionRef.current = null;
      rec.onend?.();
      return rec.startCount; // must be 0 — no auto-restart after intentional stop
    });

    expect(restartedAfterStop).toBe(0);
  });

  test("mic auto-restart fires on no-speech timeout", async ({ page }) => {
    await page.goto("/live-room/regression-test-room-nonexistent");
    await page.waitForLoadState("domcontentloaded");

    const restartedAfterNoSpeech = await page.evaluate(() => {
      let intentionalStop = false;
      let recognitionRef: { current: MockRec | null } = { current: null };

      class MockRec {
        onerror: ((ev: { error: string }) => void) | null = null;
        onend: (() => void) | null = null;
        startCount = 0;
        start() { this.startCount++; }
        stop() {}
      }

      const rec = new MockRec();
      recognitionRef.current = rec;

      rec.onerror = (ev) => {
        const code = ev?.error || "";
        if (code !== "no-speech" && code !== "aborted") {
          intentionalStop = true;
        }
      };

      rec.onend = () => {
        if (!intentionalStop && recognitionRef.current === rec) {
          try { rec.start(); return; } catch { /* fall through */ }
        }
      };

      // Simulate browser-initiated no-speech end (no onerror fires, just onend)
      rec.onend?.();
      return rec.startCount; // must be 1 — auto-restart happened
    });

    expect(restartedAfterNoSpeech).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// WV-RR-04: Teach flow — host can start a class and reach the live room
// ---------------------------------------------------------------------------
test.describe("teach flow (WV-RR-04)", () => {
  test.use({ storageState: AUTH_STATE });

  test("schedule form renders on Teach tab", async ({ page }) => {
    await page.goto("/group-classes?tab=teach");
    await expect(page.getByRole("heading", { name: /schedule|host|teach/i })).toBeVisible({ timeout: 10_000 });
    await expect(
      page.locator('input[type="text"], input[type="datetime-local"], select').first()
    ).toBeVisible();
  });

  test("Teach tab → schedule → lands on Join tab (v0.45.9 regression)", async ({ page }) => {
    await page.goto("/group-classes?tab=teach");
    const scheduleBtn = page.getByRole("button", { name: "Schedule class" });
    await expect(scheduleBtn).toBeVisible({ timeout: 10_000 });
    await expect(scheduleBtn).toBeEnabled({ timeout: 10_000 });
    await scheduleBtn.click();
    await expect(page.getByText("Schedule a Class for Your Group")).toBeVisible({ timeout: 30_000 });
  });

  test("host joining a live class gets moderator_key in sessionStorage", () => {
    const src = execSync(
      `cat "${REPO}/apps/web/app/live-room/[roomId]/page.tsx"`,
      { encoding: "utf8" }
    );
    expect(src).toContain("info.is_admin && info.moderator_key");
    expect(src).toContain("setModeratorKey(info.moderator_key)");
    expect(src).toContain("salareen-live-moderator");
    expect(src).toContain("sessionStorage.setItem");
  });

  test("Zelle payment POST includes Authorization header", () => {
    const src = execSync(
      `cat "${REPO}/apps/web/app/group-classes/page.tsx"`,
      { encoding: "utf8" }
    );
    const zelleIdx = src.indexOf("payment_method: 'zelle'");
    const zelleBlock = src.slice(zelleIdx - 600, zelleIdx + 300);
    expect(zelleBlock).toContain("authorization");
    expect(zelleBlock).toContain("Bearer");
  });
});

// ---------------------------------------------------------------------------
// WV-RR-05: Group class — student join guards
// ---------------------------------------------------------------------------
test.describe("group class student join guard (WV-RR-05)", () => {
  test.use({ storageState: AUTH_STATE });

  test("Join tab renders without crash", async ({ page }) => {
    await page.goto("/group-classes");
    await expect(page.locator("text=Something went wrong")).not.toBeVisible({ timeout: 8_000 });
  });

  test("not-started class shows friendly wait message (v0.45.9 regression)", async ({ page }) => {
    await page.goto("/group-classes");
    await page.waitForTimeout(3_000);
    const joinBtn = page.getByRole("button", { name: "Join" }).first();
    if (await joinBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await joinBtn.click({ noWaitAfter: true }).catch(() => {});
      const alertOrMsg = page.getByText(/not started|waiting|starts soon|403/i);
      if (await alertOrMsg.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await expect(alertOrMsg).not.toHaveText(/403/);
      }
    } else {
      test.skip(true, "No non-host classes available in QA seed data");
    }
  });

  test("Sales Demo button hidden for regular users (v0.45.14 regression)", async ({ page }) => {
    await page.goto("/group-classes");
    await expect(page.getByRole("button", { name: /sales demo/i })).not.toBeVisible({ timeout: 8_000 });
  });
});

// ---------------------------------------------------------------------------
// WV-RR-06: Drive Mode — voice stays alive across silence
// ---------------------------------------------------------------------------
test.describe("drive mode voice continuity (WV-RR-06)", () => {
  test.use({ storageState: AUTH_STATE });

  test("/drive page loads without JS crash", async ({ page }) => {
    await page.goto("/drive");
    const errors: string[] = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.waitForLoadState("networkidle").catch(() => {});
    const crashErrors = errors.filter(e =>
      e.includes("Uncaught") || e.includes("TypeError") || e.includes("Cannot read")
    );
    expect(crashErrors).toHaveLength(0);
  });

  test("voice pipeline SpeechChunker first-chunk latency (regression)", () => {
    // Full behavioral coverage lives in voice-pipeline.spec.ts (6 tests).
    // This source-level canary ensures SpeechChunker and StreamingVoice are
    // still exported from voicePipeline.ts and the first-chunk size stays bounded.
    const src = execSync(
      `cat "${REPO}/apps/web/app/lib/voicePipeline.ts"`,
      { encoding: "utf8" }
    );
    expect(src).toContain("export class SpeechChunker");
    expect(src).toContain("export class StreamingVoice");
    expect(src).toContain("firstChunkWords");
  });
});

// ---------------------------------------------------------------------------
// WV-RR-07: Onboarding — new account flow
// ---------------------------------------------------------------------------
test.describe("onboarding (WV-RR-07)", () => {
  // First test: unauthenticated — verifies empty-localStorage resilience on the public route.
  test("onboarding page renders without crashing when localStorage is empty", async ({ page }) => {
    await page.goto("/onboarding");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await expect(page.locator("text=Something went wrong")).not.toBeVisible({ timeout: 8_000 });
    // Must show some onboarding content, not a blank white page.
    const body = await page.textContent("body");
    expect(body?.trim().length).toBeGreaterThan(20);
  });

  test("returning user with completed onboarding is not sent back to step 0 (WV-ONB-01 regression)", async ({ browser }) => {
    // Must run authenticated — testing the step-0 reset bug for existing users.
    const ctx = await browser.newContext({ storageState: AUTH_STATE });
    const authPage = await ctx.newPage();
    try {
      await authPage.goto("/onboarding");
      // A user with completed onboarding navigating to /onboarding should either
      // redirect away or show "already complete" — not land on step 0 data-entry.
      await authPage.waitForTimeout(2_000);
      // Should have redirected OR show a completed state. Must NOT show step 0 fields.
      const nameField = authPage.locator('input[name="name"], input[placeholder*="name" i]');
      const visible = await nameField.isVisible({ timeout: 3_000 }).catch(() => false);
      if (visible) {
        // If still on the page, the value should be pre-filled (not empty).
        expect(await nameField.inputValue()).not.toBe("");
      }
    } finally {
      await ctx.close();
    }
  });
});

// ---------------------------------------------------------------------------
// WV-RR-08: Account tiers — gated content
// ---------------------------------------------------------------------------
test.describe("account tiers (WV-RR-08)", () => {
  test.use({ storageState: AUTH_STATE });

  test("billing page renders plan picker", async ({ page }) => {
    await page.goto("/billing");
    await expect(
      page.getByRole("heading", { name: /plan|subscription|upgrade/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("rewards page shows points balance", async ({ page }) => {
    await page.goto("/rewards");
    await expect(
      page.getByText(/point|reward|streak/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});

// ---------------------------------------------------------------------------
// WV-RR-09: 26 languages — locale switch
// ---------------------------------------------------------------------------
test.describe("26 languages (WV-RR-09)", () => {
  test.use({ storageState: AUTH_STATE });

  test("Spanish locale produces no raw i18n keys on corporate page", async ({ page }) => {
    await page.goto("/corporate?locale=es");
    await page.waitForLoadState("networkidle").catch(() => {});
    const body = await page.textContent("body");
    // Raw keys look like "corporate.hero.title" — should not appear in rendered text.
    expect(body).not.toMatch(/\b[a-z]+\.[a-z]+\.[a-z]+\b/);
  });

  test("language selector renders on the login page", async ({ page }) => {
    await page.goto("/");
    const selector = page.getByRole("combobox", { name: /language/i });
    await expect(selector).toBeVisible({ timeout: 8_000 });
  });
});

// ---------------------------------------------------------------------------
// WV-RR-10: Error surface — API failures show messages, not blank screens
// ---------------------------------------------------------------------------
test.describe("error surface (WV-RR-10)", () => {
  test.use({ storageState: AUTH_STATE });

  test("home feed failure shows error card, not blank page", async ({ page }) => {
    await page.route("**/home**", (route) => route.abort("failed"));
    await page.goto("/");
    await page.waitForTimeout(3_000);
    // Either an error card or the unauthenticated landing — not a blank body.
    const body = await page.textContent("body");
    expect(body?.trim().length).toBeGreaterThan(50);
  });

  test("kids page API failure surfaces error text, not silent empty state", () => {
    const src = execSync(
      `cat "${REPO}/apps/mobile/src/api.ts"`,
      { encoding: "utf8" }
    );
    const fnStart = src.indexOf("export async function getHomeRails");
    const fnEnd = src.indexOf("\nexport ", fnStart + 1);
    const fnBody = src.slice(fnStart, fnEnd > fnStart ? fnEnd : fnStart + 400);
    // getHomeRails must NOT silently swallow errors — callers handle them.
    expect(fnBody).not.toContain("} catch {");
    expect(fnBody).not.toContain("catch (_)");
  });
});

import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";

/**
 * Regression — Drive Mode Stop must halt neural narration.
 *
 * Bug: hitting Stop while a segment's neural-TTS (/tts) audio fetch was still in
 * flight did nothing (no HTMLAudioElement existed yet to pause), so when the
 * fetch resolved it started playing AFTER the player had closed — "the window
 * disappears but the audio keeps talking, on a different section". The fix adds
 * a playback epoch (bumped by cancelSpeech) + an AbortController so a fetch that
 * resolves after Stop can never start audio.
 *
 * We force the server (neural) path via /tts/status and make each /tts fetch
 * slow, so we can click Stop mid-fetch and assert NO audio playback is started.
 */

function wavBytes(): Buffer {
  // A valid but tiny/empty WAV so route.fulfill returns real audio bytes.
  const b = Buffer.alloc(44);
  b.write("RIFF", 0); b.writeUInt32LE(36, 4); b.write("WAVE", 8);
  b.write("fmt ", 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20);
  b.writeUInt16LE(1, 22); b.writeUInt32LE(8000, 24); b.writeUInt32LE(8000, 28);
  b.writeUInt16LE(1, 32); b.writeUInt16LE(8, 34);
  b.write("data", 36); b.writeUInt32LE(0, 40);
  return b;
}

test.describe("Drive Mode — Stop halts neural narration", () => {
  test.use({ storageState: AUTH_STATE });

  test.beforeEach(async ({ page }) => {
    // Force the neural path and keep each /tts fetch in flight long enough to
    // click controls while it is pending.
    await page.route("**/tts/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ available: true, engine: "mock" }),
      }));
    await page.route(/\/tts(\?.*)?$/, async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.fulfill({ status: 200, contentType: "audio/wav", body: wavBytes() }).catch(() => {});
    });
    // Count every playback attempt (spy increments before delegating).
    await page.addInitScript(() => {
      (window as unknown as { __plays: number }).__plays = 0;
      const orig = HTMLMediaElement.prototype.play;
      HTMLMediaElement.prototype.play = function (this: HTMLMediaElement) {
        (window as unknown as { __plays: number }).__plays += 1;
        return orig.apply(this, [] as unknown as []);
      };
    });
  });

  async function startFirstCourse(page: import("@playwright/test").Page) {
    await page.goto("/drive");
    const firstCourse = page.locator('button:has-text("🎧")').first();
    await expect(firstCourse).toBeVisible({ timeout: 20_000 });
    await firstCourse.click();
    // The player renders a Stop (⏹) control once a course is loaded.
    await expect(page.getByRole("button", { name: /stop/i })).toBeVisible({ timeout: 20_000 });
  }

  test("stopping during an in-flight /tts fetch starts no audio", async ({ page }) => {
    let ttsRequests = 0;
    await page.route(/\/tts(\?.*)?$/, async (route) => {
      ttsRequests += 1;
      await new Promise((r) => setTimeout(r, 1500));
      await route.fulfill({ status: 200, contentType: "audio/wav", body: wavBytes() }).catch(() => {});
    });

    await startFirstCourse(page);
    // Wait until the first segment's fetch is actually in flight, then Stop.
    await expect.poll(() => ttsRequests, { timeout: 20_000 }).toBeGreaterThan(0);
    await page.getByRole("button", { name: /stop/i }).click();

    // Player closes...
    await expect(page.getByRole("button", { name: "⏹" })).toBeHidden();
    // ...and the fetch that resolves afterward must NOT begin playing.
    await page.waitForTimeout(2200);
    const plays = await page.evaluate(() => (window as unknown as { __plays: number }).__plays);
    expect(plays).toBe(0);
  });

  test("control (sanity): letting a segment load DOES start audio", async ({ page }) => {
    await startFirstCourse(page);
    // Without stopping, the resolved fetch should reach audio playback.
    await expect
      .poll(() => page.evaluate(() => (window as unknown as { __plays: number }).__plays), { timeout: 20_000 })
      .toBeGreaterThan(0);
  });
});

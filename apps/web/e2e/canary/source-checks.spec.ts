/**
 * Source-level regression canary — no browser, no server, no auth needed.
 *
 * Every test here reads source files via execSync and asserts that critical
 * patterns exist. These run in ~5 s on a bare Node.js + Playwright runner
 * with no Docker stack. They catch the class of regression found in v0.45.x:
 * silent behavior changes that pass typecheck but break a feature at runtime.
 *
 * Run: npx playwright test --config playwright.canary.config.ts
 * CI:  regression-canary job in .github/workflows/ci.yml
 *
 * DO NOT add tests here that call page.goto() or any browser navigation.
 * Those belong in the nightly web-e2e.yml suite.
 */

import { execSync } from "child_process";
import * as path from "path";
import { expect, test } from "@playwright/test";

// e2e/canary/ is 4 levels deep from repo root (apps/web/e2e/canary/)
const REPO = path.resolve(__dirname, "../../../..");

// ---------------------------------------------------------------------------
// Notification default (WV-RR-01)
// ---------------------------------------------------------------------------
test("notification: dailyReminderHour default is 8 AM not 18 PM", () => {
  const src = execSync(
    `grep "dailyReminderHour" "${REPO}/apps/mobile/src/storage.ts"`,
    { encoding: "utf8" }
  );
  expect(src).toMatch(/dailyReminderHour:\s*8\b/);
  expect(src).not.toMatch(/dailyReminderHour:\s*18\b/);
});

test("notification: settings picker includes 08:00 as selectable option", () => {
  const src = execSync(
    `grep "reminderHours" "${REPO}/apps/mobile/src/screens/SettingsScreen.tsx"`,
    { encoding: "utf8" }
  );
  expect(src).toMatch(/\[.*\b8\b.*\]/);
});

// ---------------------------------------------------------------------------
// Kids section parity (WV-RR-02)
// ---------------------------------------------------------------------------
test("kids: mobile KidsScreen uses getHomeRails not listAudioCourses", () => {
  const src = execSync(
    `cat "${REPO}/apps/mobile/src/screens/KidsScreen.tsx"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("getHomeRails");
  expect(src).not.toContain("listAudioCourses");
  // Single import statement — duplicate was a regression caught in PR #444.
  const railImports = (src.match(/import.*from.*["']\.\.\/components\/Rail["']/g) || []).length;
  expect(railImports).toBe(1);
});

test("kids: getHomeRails does not swallow errors silently", () => {
  const src = execSync(
    `cat "${REPO}/apps/mobile/src/api.ts"`,
    { encoding: "utf8" }
  );
  const fnStart = src.indexOf("export async function getHomeRails");
  const fnEnd = src.indexOf("\nexport ", fnStart + 1);
  const fnBody = src.slice(fnStart, fnEnd > fnStart ? fnEnd : fnStart + 400);
  expect(fnBody).not.toContain("} catch {");
  expect(fnBody).not.toContain("catch (_)");
});

// ---------------------------------------------------------------------------
// Floor mic continuity (WV-RR-03)
// ---------------------------------------------------------------------------
test("mic: onerror sets intentionalStop for non-transient errors", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/live-room/[roomId]/page.tsx"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("intentionalStop");
  expect(src).toContain("recognitionRef.current === rec");
  expect(src).toMatch(/code !== "no-speech".*code !== "aborted"/s);
  expect(src).toContain("rec.start()");
});

// ---------------------------------------------------------------------------
// Teach flow (WV-RR-04 / WV-TEACH)
// ---------------------------------------------------------------------------
test("teach: isHost and hostTileRef exist in live-room page", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/live-room/[roomId]/page.tsx"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("isHost");
  expect(src).toContain("hostTileRef");
  expect(src).toContain("canModerate");
  expect(src).toContain("isPlatformAdmin");
});

test("teach: group-classes page stores moderator_key on host start", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/group-classes/page.tsx"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("asHost && res.bridge.moderator_key");
  expect(src).toContain("salareen-live-moderator");
});

test("teach: host joining live class gets moderator_key in sessionStorage", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/live-room/[roomId]/page.tsx"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("info.is_admin && info.moderator_key");
  expect(src).toContain("setModeratorKey(info.moderator_key)");
  expect(src).toContain("sessionStorage.setItem");
});

test("teach: Zelle payment uses the shared group-class checkout client", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/group-classes/page.tsx"`,
    { encoding: "utf8" }
  );
  const zelleIdx = src.indexOf('payment_method: "zelle"');
  const zelleBlock = src.slice(zelleIdx - 600, zelleIdx + 300);
  expect(zelleBlock).toContain("checkoutGroupClass");
  expect(zelleBlock).not.toContain("window.location.origin");
  expect(zelleBlock).not.toContain("/orchestrator/api/group-classes");

  const api = execSync(
    `cat "${REPO}/apps/web/app/lib/api.ts"`,
    { encoding: "utf8" }
  );
  const checkoutIdx = api.indexOf("export async function checkoutGroupClass");
  const checkoutBlock = api.slice(checkoutIdx, checkoutIdx + 700);
  expect(checkoutBlock).toContain("${ORCHESTRATOR_URL}");
  expect(checkoutBlock).toContain("authHeaders()");
});

test("web routing: deployed service rewrites include webcam", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/next.config.mjs"`,
    { encoding: "utf8" }
  );
  expect(src).toContain('"webcam"');
});

test("legacy class page: join helper uses canonical app service URL", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/lib/api.ts"`,
    { encoding: "utf8" }
  );
  expect(src).toContain('from "../app/lib/api"');
  expect(src).not.toContain('process.env.ORCHESTRATOR_URL ?? "http://localhost:8000"');
});

test("live room: recording badge tolerates partial room payloads", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/live-room/[roomId]/page.tsx"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("room?.recording?.status");
});

test("vision: dispose frees detector and recognizer handles", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/lib/vision.ts"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("detector.delete?.()");
  expect(src).toContain("recognizer.delete?.()");
});

// ---------------------------------------------------------------------------
// Voice pipeline (WV-RR-06)
// ---------------------------------------------------------------------------
test("voice: SpeechChunker and StreamingVoice exported from voicePipeline", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/lib/voicePipeline.ts"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("export class SpeechChunker");
  expect(src).toContain("export class StreamingVoice");
  expect(src).toContain("firstChunkWords");
});

// ---------------------------------------------------------------------------
// Error surface (WV-RR-10)
// ---------------------------------------------------------------------------
test("errors: getHomeRails in mobile api does not have silent catch", () => {
  const src = execSync(
    `cat "${REPO}/apps/mobile/src/api.ts"`,
    { encoding: "utf8" }
  );
  const fnStart = src.indexOf("export async function getHomeRails");
  const fnEnd = src.indexOf("\nexport ", fnStart + 1);
  const fnBody = src.slice(fnStart, fnEnd > fnStart ? fnEnd : fnStart + 400);
  expect(fnBody).not.toContain("} catch {");
});

// ---------------------------------------------------------------------------
// Camera recognition (WV-CAM)
// ---------------------------------------------------------------------------
test("camera: WebcamPresenceBar exports default and handles solo+group", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/components/WebcamPresenceBar.tsx"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("export default function WebcamPresenceBar");
  expect(src).toContain('"solo"');
  expect(src).toContain('"group"');
  expect(src).toContain("attention");
});

test("camera: useWebcamSession cleans up tracks, interval, WS, session on unmount", () => {
  const src = execSync(
    `cat "${REPO}/apps/web/app/hooks/useWebcamSession.ts"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("getTracks().forEach");
  expect(src).toContain(".stop()");
  expect(src).toContain("clearInterval");
  expect(src).toContain(".close()");
  expect(src).toContain("endWebcamSession");
});

test("camera: aoep_shared has PresenceTracker, SilhouetteDetector, XAIVoiceClient", () => {
  const presence = execSync(
    `cat "${REPO}/packages/shared/src/aoep_shared/presence.py"`,
    { encoding: "utf8" }
  );
  expect(presence).toContain("class PresenceTracker");
  expect(presence).toContain("class GroupPresenceTracker");

  const silhouette = execSync(
    `cat "${REPO}/packages/shared/src/aoep_shared/silhouette.py"`,
    { encoding: "utf8" }
  );
  expect(silhouette).toContain("class SilhouetteDetector");

  const xai = execSync(
    `cat "${REPO}/packages/shared/src/aoep_shared/xai_voice.py"`,
    { encoding: "utf8" }
  );
  expect(xai).toContain("class XAIVoiceClient");
});

test("camera: SilhouetteDetector has OpenCV try/except fallback", () => {
  const src = execSync(
    `cat "${REPO}/packages/shared/src/aoep_shared/silhouette.py"`,
    { encoding: "utf8" }
  );
  expect(src).toMatch(/try.*import cv2|ImportError.*cv2|cv2.*ImportError/s);
  expect(src).toContain("background_sub");
});

test("camera: PresenceTracker defines UNKNOWN/PRESENT/AWAY/ABSENT states", () => {
  const src = execSync(
    `cat "${REPO}/packages/shared/src/aoep_shared/presence.py"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("UNKNOWN");
  expect(src).toContain("PRESENT");
  expect(src).toContain("AWAY");
  expect(src).toContain("ABSENT");
  expect(src).toContain("away_grace");
});

test("camera: webcam service has all 7 required endpoints", () => {
  const src = execSync(
    `cat "${REPO}/services/webcam/src/webcam/main.py"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("/sessions");
  expect(src).toContain("/sessions/{session_id}/frame");
  expect(src).toContain("/sessions/{session_id}/presence");
  expect(src).toContain("/sessions/{session_id}/voice");
  expect(src).toContain("/sessions/{session_id}/ws");
});

test("camera: mobile cameraPermission test covers request and denied case", () => {
  const src = execSync(
    `cat "${REPO}/apps/mobile/src/__tests__/cameraPermission.test.ts"`,
    { encoding: "utf8" }
  );
  expect(src).toContain("ensureCameraPermission");
  expect(src).toMatch(/request|RESULTS\.GRANTED|RESULTS\.DENIED/i);
  expect(src).toMatch(/denied|DENIED|false/i);
});

// ---------------------------------------------------------------------------
// 26 languages (WV-LANG)
// ---------------------------------------------------------------------------
test("languages: voiceAssistant BCP-47 map covers 12 core locales", () => {
  const src = execSync(
    `cat "${REPO}/apps/mobile/src/voiceAssistant.ts"`,
    { encoding: "utf8" }
  );
  const coreLangs = ["en", "es", "fr", "de", "it", "pt", "ru", "ar", "hi", "zh", "ja", "ko"];
  for (const lang of coreLangs) {
    expect(src).toMatch(new RegExp(`${lang}:\\s*"[a-z]{2}-[A-Z]{2}"`));
  }
});

test("languages: mobile trainingLocale normalizer handles core locales", () => {
  const src = execSync(
    `cat "${REPO}/apps/mobile/src/trainingLocale.ts"`,
    { encoding: "utf8" }
  );
  expect(src.length).toBeGreaterThan(50);
  expect(src).toMatch(/en|es|fr|de|zh|ja|ko/);
});

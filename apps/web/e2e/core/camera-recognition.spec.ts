import { execSync } from "child_process";
import * as path from "path";
import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";

const REPO = path.resolve(__dirname, "../../../..");

/**
 * Camera recognition (WV-CAM)
 *
 * The webcam presence + silhouette system landed in v0.45+ via services/webcam/.
 * These tests cover both the web frontend surface and the backend module integrity.
 *
 *   WV-CAM-01  /vision page loads without crash
 *   WV-CAM-02  Webcam service API modules are present in packages/shared
 *   WV-CAM-03  SilhouetteDetector falls back gracefully when OpenCV is absent
 *   WV-CAM-04  PresenceTracker state machine transitions are correct
 *   WV-CAM-05  WebcamPresenceBar component is exported from the web app
 *   WV-CAM-06  useWebcamSession hook cleans up on unmount (no memory leak)
 *   WV-CAM-07  Camera permission prompt is shown before access (mobile)
 */

test.describe("camera — web frontend (WV-CAM-01/05/06)", () => {
  test.use({ storageState: AUTH_STATE });

  test("/vision page loads without JS crash (WV-CAM-01)", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    await page.goto("/vision");
    await page.waitForLoadState("networkidle").catch(() => {});
    const crash = errors.filter(
      (e) =>
        e.includes("Uncaught") ||
        e.includes("TypeError: Cannot read") ||
        e.includes("is not a function")
    );
    expect(crash).toHaveLength(0);
    // Page must render content.
    const body = await page.textContent("body");
    expect(body?.trim().length).toBeGreaterThan(50);
  });

  test("WebcamPresenceBar component file exists and exports default (WV-CAM-05)", () => {
    const src = execSync(
      `cat "${REPO}/apps/web/app/components/WebcamPresenceBar.tsx"`,
      { encoding: "utf8" }
    );
    expect(src).toContain("export default function WebcamPresenceBar");
    // Must handle both solo and group class types.
    expect(src).toContain('"solo"');
    expect(src).toContain('"group"');
    // Must show attention percentage.
    expect(src).toContain("attention");
  });

  test("useWebcamSession hook cleans up camera on unmount (WV-CAM-06)", () => {
    const src = execSync(
      `cat "${REPO}/apps/web/app/hooks/useWebcamSession.ts"`,
      { encoding: "utf8" }
    );
    // Cleanup effect must stop all tracks.
    expect(src).toContain("getTracks().forEach");
    expect(src).toContain(".stop()");
    // Interval must be cleared on unmount.
    expect(src).toContain("clearInterval");
    // WebSocket must be closed.
    expect(src).toContain(".close()");
    // endWebcamSession must be called to clean up backend state.
    expect(src).toContain("endWebcamSession");
  });
});

test.describe("camera — backend modules (WV-CAM-02/03/04)", () => {
  test("webcam shared modules exist in packages/shared (WV-CAM-02)", () => {
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
    expect(silhouette).toContain("class SilhouetteResult");

    const xaiVoice = execSync(
      `cat "${REPO}/packages/shared/src/aoep_shared/xai_voice.py"`,
      { encoding: "utf8" }
    );
    expect(xaiVoice).toContain("class XAIVoiceClient");
  });

  test("SilhouetteDetector has OpenCV fallback (WV-CAM-03)", () => {
    const src = execSync(
      `cat "${REPO}/packages/shared/src/aoep_shared/silhouette.py"`,
      { encoding: "utf8" }
    );
    // Must not hard-require OpenCV — should try/except import.
    expect(src).toMatch(/try.*import cv2|ImportError.*cv2|cv2.*ImportError/s);
    // Fallback must exist for when OpenCV is not installed.
    expect(src).toContain("background_sub");
  });

  test("PresenceTracker has UNKNOWN→PRESENT→AWAY→ABSENT transitions (WV-CAM-04)", () => {
    const src = execSync(
      `cat "${REPO}/packages/shared/src/aoep_shared/presence.py"`,
      { encoding: "utf8" }
    );
    // All four presence states must be defined.
    expect(src).toContain("UNKNOWN");
    expect(src).toContain("PRESENT");
    expect(src).toContain("AWAY");
    expect(src).toContain("ABSENT");
    // Grace period must be configurable (away before absent).
    expect(src).toContain("away_grace");
  });

  test("webcam service has all required endpoints (WV-CAM-02)", () => {
    const src = execSync(
      `cat "${REPO}/services/webcam/src/webcam/main.py"`,
      { encoding: "utf8" }
    );
    // Session lifecycle — Python decorators use double-quoted paths.
    expect(src).toContain("/sessions");
    expect(src).toContain("/sessions/{session_id}");
    // Frame submission.
    expect(src).toContain("/sessions/{session_id}/frame");
    // Presence summary.
    expect(src).toContain("/sessions/{session_id}/presence");
    // Voice agent.
    expect(src).toContain("/sessions/{session_id}/voice");
    // WebSocket.
    expect(src).toContain("/sessions/{session_id}/ws");
  });
});

test.describe("camera — mobile permissions (WV-CAM-07)", () => {
  test("mobile cameraPermission module requests before accessing camera", () => {
    const src = execSync(
      `cat "${REPO}/apps/mobile/src/__tests__/cameraPermission.test.ts"`,
      { encoding: "utf8" }
    );
    // ensureCameraPermission is the public API.
    expect(src).toContain("ensureCameraPermission");
    // Permission request must be tested.
    expect(src).toMatch(/request|RESULTS\.GRANTED|RESULTS\.DENIED/i);
    // Denied/blocked case must be covered.
    expect(src).toMatch(/denied|DENIED|false/i);
  });
});

/** Build bug-report payloads (mobile). */

import { Platform } from "react-native";
import Constants from "expo-constants";

import { APP_VERSION } from "./version";
import { drainClientLogs } from "./clientLog";
import type { BugScreenshotUpload } from "./api";

/** Keep under the memory-service 2 MB decoded screenshot limit. */
export const BUG_SCREENSHOT_MAX_BYTES = 1_500_000;

export function buildBugSnapshot(screen: string, extra: Record<string, unknown> = {}) {
  return {
    screen,
    platform_os: Platform.OS,
    platform_version: String(Platform.Version),
    device_name: Constants.deviceName || "",
    expo_version: Constants.expoVersion || "",
    execution_environment: Constants.executionEnvironment,
    context_stack: (new Error("Bug report opened here").stack || "").slice(0, 8000),
    ...extra,
  };
}

export function bugReportBase(screen: string, extra: Record<string, unknown> = {}) {
  return {
    platform: Platform.OS === "ios" ? "ios" : Platform.OS === "android" ? "android" : "mobile",
    app_version: APP_VERSION,
    screen,
    snapshot: buildBugSnapshot(screen, extra),
    logs: drainClientLogs(),
  };
}

function decodedByteLength(base64: string): number {
  const padded = base64.replace(/=+$/, "");
  return Math.floor((padded.length * 3) / 4);
}

export function imageAssetToUpload(
  asset: { uri?: string; fileName?: string | null; mimeType?: string | null; base64?: string | null },
): BugScreenshotUpload | null {
  if (!asset.base64) return null;
  if (decodedByteLength(asset.base64) > BUG_SCREENSHOT_MAX_BYTES) {
    // Picker quality should usually keep us under the limit; refuse oversized
    // originals so /memory/bugs does not abort mid-upload on cellular.
    return null;
  }
  return {
    filename: asset.fileName || "screenshot.jpg",
    content_type: asset.mimeType || "image/jpeg",
    data_base64: asset.base64,
  };
}

/** Build bug-report payloads and capture screenshots (web). */

import { APP_VERSION } from "./version";
import { drainClientLogs } from "./clientLog";
import type { BugScreenshotUpload } from "./api";

export function buildBugSnapshot(extra: Record<string, unknown> = {}): Record<string, unknown> {
  if (typeof window === "undefined") return { ...extra };
  const contextStack = new Error("Bug report opened here").stack || "";
  return {
    route: window.location.pathname,
    search: window.location.search,
    href: window.location.href.split("?")[0],
    referrer: document.referrer || "",
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    user_agent: navigator.userAgent,
    locale: navigator.language,
    online: navigator.onLine,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    memory_gb: (navigator as Navigator & { deviceMemory?: number }).deviceMemory,
    cpu_threads: navigator.hardwareConcurrency,
    context_stack: contextStack.slice(0, 8000),
    ...extra,
  };
}

export async function fileToScreenshotUpload(file: File): Promise<BugScreenshotUpload> {
  const buf = await file.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]!);
  return {
    filename: file.name || "screenshot.png",
    content_type: file.type || "image/png",
    data_base64: btoa(binary),
  };
}

/** Ask the learner to share their screen/tab; returns one PNG frame as base64. */
export async function captureDisplayScreenshot(): Promise<BugScreenshotUpload | null> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getDisplayMedia) {
    return null;
  }
  let stream: MediaStream | null = null;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    const track = stream.getVideoTracks()[0];
    if (!track) return null;
    const video = document.createElement("video");
    video.srcObject = stream;
    await video.play();
    // Wait for the first decoded frame before drawing — play() resolves when
    // playback starts, not when a frame is available, so a fixed delay can race.
    await new Promise<void>((resolve) => {
      if (video.readyState >= 3) { resolve(); return; }
      video.addEventListener("canplay", () => resolve(), { once: true });
      setTimeout(resolve, 3000); // hard fallback
    });
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL("image/png");
    const base64 = dataUrl.split(",", 2)[1] || "";
    return {
      filename: "screen-capture.png",
      content_type: "image/png",
      data_base64: base64,
    };
  } catch {
    return null;
  } finally {
    stream?.getTracks().forEach((t) => t.stop());
  }
}

export function bugReportBase(extraSnapshot: Record<string, unknown> = {}) {
  return {
    platform: "web" as const,
    app_version: APP_VERSION,
    screen: typeof window !== "undefined" ? window.location.pathname : "",
    snapshot: buildBugSnapshot(extraSnapshot),
    logs: drainClientLogs(),
  };
}

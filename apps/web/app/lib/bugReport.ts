/** Build bug-report payloads and capture screenshots (web). */

import { APP_VERSION } from "./version";
import { drainClientLogs } from "./clientLog";
import type { BugScreenshotUpload } from "./api";

/** Server rejects decoded screenshots above 2_000_000 bytes. Stay under that. */
export const BUG_SCREENSHOT_MAX_BYTES = 1_500_000;
const BUG_SCREENSHOT_MAX_EDGE = 1600;

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

function decodedByteLength(base64: string): number {
  const padded = base64.replace(/=+$/, "");
  return Math.floor((padded.length * 3) / 4);
}

function dataUrlToUpload(
  dataUrl: string,
  filename: string,
): BugScreenshotUpload | null {
  const match = /^data:([^;]+);base64,(.+)$/.exec(dataUrl);
  if (!match) return null;
  return {
    filename,
    content_type: match[1] || "image/jpeg",
    data_base64: match[2] || "",
  };
}

/**
 * Downscale + JPEG-compress a canvas/image so the JSON POST to /memory/bugs
 * stays under the server's 2 MB decoded-attachment limit. Uncompressed PNG
 * captures of retina/desktop screens (and camera roll photos) were large enough
 * to abort the request mid-flight ("network connection was lost").
 */
export async function compressScreenshotUpload(
  source: CanvasImageSource,
  opts: {
    filename?: string;
    sourceWidth: number;
    sourceHeight: number;
    maxBytes?: number;
    maxEdge?: number;
  },
): Promise<BugScreenshotUpload | null> {
  const maxBytes = opts.maxBytes ?? BUG_SCREENSHOT_MAX_BYTES;
  const maxEdge = opts.maxEdge ?? BUG_SCREENSHOT_MAX_EDGE;
  const srcW = Math.max(1, opts.sourceWidth | 0);
  const srcH = Math.max(1, opts.sourceHeight | 0);
  const scale = Math.min(1, maxEdge / Math.max(srcW, srcH));
  const width = Math.max(1, Math.round(srcW * scale));
  const height = Math.max(1, Math.round(srcH * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(source, 0, 0, width, height);

  const filename = opts.filename || "screenshot.jpg";
  for (const quality of [0.72, 0.58, 0.45, 0.32]) {
    const dataUrl = canvas.toDataURL("image/jpeg", quality);
    const upload = dataUrlToUpload(dataUrl, filename);
    if (!upload?.data_base64) continue;
    if (decodedByteLength(upload.data_base64) <= maxBytes) return upload;
  }
  // Last resort: shrink further and try once more.
  canvas.width = Math.max(1, Math.round(width * 0.55));
  canvas.height = Math.max(1, Math.round(height * 0.55));
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  const fallback = dataUrlToUpload(canvas.toDataURL("image/jpeg", 0.4), filename);
  if (!fallback?.data_base64) return null;
  if (decodedByteLength(fallback.data_base64) > maxBytes) return null;
  return fallback;
}

async function loadImageElement(src: string): Promise<HTMLImageElement> {
  const img = new Image();
  img.decoding = "async";
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error("Could not decode that image"));
    img.src = src;
  });
  return img;
}

export async function fileToScreenshotUpload(file: File): Promise<BugScreenshotUpload> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const img = await loadImageElement(objectUrl);
    const compressed = await compressScreenshotUpload(img, {
      filename: (file.name || "screenshot").replace(/\.[^.]+$/, "") + ".jpg",
      sourceWidth: img.naturalWidth || img.width,
      sourceHeight: img.naturalHeight || img.height,
    });
    if (compressed) return compressed;
    throw new Error(
      "That screenshot is too large to send. Try a smaller crop, or send the report without a screenshot.",
    );
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

/** Ask the learner to share their screen/tab; returns one compressed JPEG frame. */
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
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    return await compressScreenshotUpload(video, {
      filename: "screen-capture.jpg",
      sourceWidth: width,
      sourceHeight: height,
    });
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

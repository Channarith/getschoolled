/** On-device face presence for On the Go. Nothing here sends a frame anywhere: frames go to the browser's own detector only. */

export type PresenceEvent = "away" | "back" | null;

/**
 * Debounced presence: "away" after the face has been missing for awayAfterMs, "back" after it has been seen again for backAfterMs.
 * A blink, a turned head or one dropped frame must not pause the lesson.
 */
export class PresenceTracker {
  private present = true;           // assume present until proven otherwise
  private since = 0;                // when the current raw reading started
  private lastRaw: boolean | null = null;

  private readonly awayAfterMs: number;
  private readonly backAfterMs: number;

  constructor(awayAfterMs = 4000, backAfterMs = 700) {
    this.awayAfterMs = awayAfterMs;
    this.backAfterMs = backAfterMs;
  }

  get isPresent(): boolean { return this.present; }

  update(rawPresent: boolean, nowMs: number): PresenceEvent {
    if (this.lastRaw !== rawPresent) {
      this.lastRaw = rawPresent;
      this.since = nowMs;
    }
    const held = nowMs - this.since;
    if (this.present && !rawPresent && held >= this.awayAfterMs) {
      this.present = false;
      return "away";
    }
    if (!this.present && rawPresent && held >= this.backAfterMs) {
      this.present = true;
      return "back";
    }
    return null;
  }

  reset(): void { this.present = true; this.lastRaw = null; this.since = 0; }
}

export type FaceReading = { present: boolean };
export type FaceSource = { detect(video: HTMLVideoElement, nowMs: number): Promise<FaceReading>; close(): void };

const VISION_BASE = "/vendor/vision";

type LandmarkerLike = { detectForVideo(v: HTMLVideoElement, ts: number): { faceLandmarks?: unknown[] }; close?: () => void };

/** MediaPipe Face Landmarker from this site's own /vendor/vision (same files Vision Play uses). */
async function mediaPipeSource(): Promise<FaceSource | null> {
  try {
    const mod: any = await import(/* webpackIgnore: true */ `${VISION_BASE}/tasks-vision.mjs`);
    const fileset = await mod.FilesetResolver.forVisionTasks(`${VISION_BASE}/wasm`);
    const make = (delegate: "GPU" | "CPU") =>
      mod.FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: `${VISION_BASE}/face_landmarker.task`, delegate },
        runningMode: "VIDEO",
        numFaces: 1,
      }) as Promise<LandmarkerLike>;
    let lm: LandmarkerLike;
    try { lm = await make("GPU"); } catch { lm = await make("CPU"); }
    let lastTs = 0;
    return {
      async detect(video, nowMs) {
        const ts = Math.max(nowMs, lastTs + 1);   // MediaPipe needs strictly increasing timestamps
        lastTs = ts;
        const res = lm.detectForVideo(video, ts);
        return { present: (res.faceLandmarks?.length ?? 0) > 0 };
      },
      close() { try { lm.close?.(); } catch { /* already closed */ } },
    };
  } catch {
    return null;
  }
}

type NativeDetector = { detect(img: CanvasImageSource): Promise<unknown[]> };

function shapeDetectionSource(): FaceSource | null {
  const FD = (globalThis as { FaceDetector?: new (o?: { maxDetectedFaces?: number; fastMode?: boolean }) => NativeDetector }).FaceDetector;
  if (!FD) return null;
  try {
    const det = new FD({ maxDetectedFaces: 1, fastMode: true });
    return {
      async detect(video) {
        const faces = await det.detect(video);
        return { present: faces.length > 0 };
      },
      close() { /* nothing to release */ },
    };
  } catch {
    return null;
  }
}

/** First working detector, or null when this browser cannot do it (the lesson then simply never auto-pauses). */
export async function createFaceSource(): Promise<FaceSource | null> {
  return (await mediaPipeSource()) ?? shapeDetectionSource();
}

export const CAMERA_PREF_KEY = "salareen.onTheGo.camera";
export const WIDGET_POS_KEY = "salareen.onTheGo.widgetPos";

/** Camera is opt-out and the choice sticks: "off" is remembered, anything else means on. */
export function cameraWanted(storage: { getItem(k: string): string | null } | null): boolean {
  try { return storage?.getItem(CAMERA_PREF_KEY) !== "off"; } catch { return true; }
}

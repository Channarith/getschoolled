// OpenCV.js runtime helpers shared by the on-device face pipeline (./vision).
//
// The official OpenCV.js 4.10.0 build is served from our own origin; the copy on
// the OpenCV docs host refuses hot-linked requests. Set NEXT_PUBLIC_OPENCV_JS_URL
// only to point at another same-origin copy of the same build.

export const OPENCV_JS_URL =
  process.env.NEXT_PUBLIC_OPENCV_JS_URL || "/opencv/4.10.0/opencv.js";

export class ModelLoadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ModelLoadError";
  }
}

/**
 * Resolve once the Emscripten runtime is ready.
 *
 * The build exposes a `then` that resolves with the module itself, so awaiting
 * it (or passing it to `resolve`) recurses forever. Drop `then` before handing
 * the module to a promise.
 */
export function waitForCvRuntime(cv: any, timeoutMs = 45_000): Promise<any> {
  return new Promise((resolve, reject) => {
    if (!cv) {
      reject(new ModelLoadError("opencv.js loaded but window.cv is undefined"));
      return;
    }
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(new ModelLoadError("The face model took too long to start."));
    }, timeoutMs);
    const ready = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (typeof cv.then === "function") {
        try {
          delete cv.then;
        } catch {
          cv.then = undefined;
        }
      }
      if (typeof cv.FaceDetectorYN !== "function" || typeof cv.readNet !== "function") {
        reject(new ModelLoadError("This OpenCV.js build lacks FaceDetectorYN; use the official 4.10.0+ build."));
        return;
      }
      resolve(cv);
    };
    if (cv.Mat) {
      ready();
      return;
    }
    const previous = cv.onRuntimeInitialized;
    cv.onRuntimeInitialized = () => {
      if (typeof previous === "function") previous();
      ready();
    };
  });
}

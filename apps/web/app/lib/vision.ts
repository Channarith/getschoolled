// On-device face pipeline (hybrid path).
//
// Detection (YuNet) + embedding (SFace) run entirely in the browser via
// OpenCV.js, so the raw camera frame never leaves the device. Only the 128-d
// embedding (+ the 5 landmarks/bbox needed for engagement) is sent to the
// perception service, which matches it against the consented gallery and
// enforces the region/consent compliance gates.
//
// This mirrors OpenCV's official js_face_recognition sample: detect with
// `cv.FaceDetectorYN`, embed by running the SFace net (`cv.readNet(...)`) on the
// resized face ROI. Because the hybrid flow enrols AND identifies through this
// same pipeline, embeddings live in one self-consistent space (cosine matching
// on the server is identical whether the vector came from here or the server
// engine).

import { visionModelUrl, type WireFace } from "./api";
import { sfaceWarpMatrix } from "./learnerCheck";
import { ModelLoadError, OPENCV_JS_URL, waitForCvRuntime } from "./opencvRuntime";
import { fetchVisionModel } from "./visionModels";

const DETECTOR_NAME = "face_detection_yunet_2023mar.onnx";
const RECOGNIZER_NAME = "face_recognition_sface_2021dec.onnx";
// Keep live browser tracking as forgiving as the mobile/server preview. The
// scan uses these landmarks only for the on-screen contour; enrollment still
// requires all pose embeddings to match before anything is uploaded.
const DET_SCORE_THRESHOLD = 0.45;
// YuNet is built for about a 320px input. Tracking uses that size so the
// eyes and nose stay on the live face. The saved embedding uses a larger
// frame so the aligned 112px crop is sharp enough to match the portrait.
const TRACK_LONG_EDGE = 256;
const EMBED_LONG_EDGE = 480;

export type ImageSource =
  | HTMLVideoElement
  | HTMLImageElement
  | HTMLCanvasElement;

export type VisionEngine = {
  /** Detect every face and return its on-device embedding + geometry. */
  detectAndEmbed: (source: ImageSource) => WireFace[];
  /**
   * Fast detect-only path: runs YuNet (face box + 5 landmarks + score) but
   * SKIPS the SFace embedding, which is a 38 MB ONNX net and the slowest
   * step on CPU. Use this for every pose-tracking tick in the scan loop
   * where only landmarks are needed; call {@link detectAndEmbed} just once
   * (when the target pose matches) to actually capture the embedding. On
   * a mid-range Mac this is ~5-8× faster than the full embed path.
   */
  detect: (source: ImageSource) => WireFace[];
  /**
   * SFace embedding for landmarks already found by {@link detect}. Skips a
   * second YuNet pass so the saved vector is the same face the oval tracked.
   */
  embedAt: (source: ImageSource, landmarks: number[][]) => number[] | null;
  /** Free native (WASM) handles. */
  dispose: () => void;
};

let _cvReady: Promise<any> | null = null;

function loadOpenCv(): Promise<any> {
  if (_cvReady) return _cvReady;
  _cvReady = new Promise<any>((resolve, reject) => {
    const w = window as any;
    if (w.cv) {
      waitForCvRuntime(w.cv).then(resolve, reject);
      return;
    }
    const script = document.createElement("script");
    script.src = OPENCV_JS_URL;
    script.async = true;
    script.onload = () => waitForCvRuntime(w.cv).then(resolve, reject);
    script.onerror = () => {
      script.remove();
      reject(new ModelLoadError(`failed to load opencv.js from ${OPENCV_JS_URL}`));
    };
    document.body.appendChild(script);
  });
  // A failed download must not poison retries for the rest of the session.
  _cvReady.catch(() => {
    _cvReady = null;
  });
  return _cvReady;
}

// The runtime's heap is fixed at 128 MB; SFace alone is ~37 MB, so each file is
// removed from the Emscripten FS once OpenCV has parsed it.
async function withStagedModel<T>(cv: any, name: string, open: () => T): Promise<T> {
  const buf = await fetchVisionModel(name, visionModelUrl(name));
  try {
    cv.FS_unlink("/" + name);
  } catch {
    /* not staged yet */
  }
  cv.FS_createDataFile("/", name, buf, true, false, false);
  try {
    return open();
  } finally {
    try {
      cv.FS_unlink("/" + name);
    } catch {
      /* best-effort */
    }
  }
}

/** Load OpenCV.js + the YuNet/SFace models and return a ready engine. */
export async function createVisionEngine(): Promise<VisionEngine> {
  const cv = await loadOpenCv();
  const detector = await withStagedModel(cv, DETECTOR_NAME, () => new cv.FaceDetectorYN(
    DETECTOR_NAME,
    "",
    new cv.Size(320, 320),
    DET_SCORE_THRESHOLD,
    0.3,
    5000
  ));
  const recognizer = await withStagedModel(cv, RECOGNIZER_NAME, () => cv.readNet(RECOGNIZER_NAME));

  const canvas = document.createElement("canvas");
  const embedCanvas = document.createElement("canvas");
  let bgr: { delete: () => void } | null = null;
  let out: { data32F: Float32Array; delete: () => void } | null = null;
  let trackWidth = 0;
  let trackHeight = 0;

  function sourceSize(source: ImageSource): [number, number] | null {
    const width =
      (source as HTMLVideoElement).videoWidth ||
      (source as HTMLImageElement).naturalWidth ||
      (source as HTMLCanvasElement).width;
    const height =
      (source as HTMLVideoElement).videoHeight ||
      (source as HTMLImageElement).naturalHeight ||
      (source as HTMLCanvasElement).height;
    return width && height ? [width, height] : null;
  }

  function drawScaled(target: HTMLCanvasElement, source: ImageSource, limit: number): [number, number, number] | null {
    const size = sourceSize(source);
    if (!size) return null;
    const [width, height] = size;
    const longEdge = Math.max(width, height);
    const scale = longEdge > limit ? limit / longEdge : 1;
    const dw = Math.max(1, Math.round(width * scale));
    const dh = Math.max(1, Math.round(height * scale));
    if (target.width !== dw) target.width = dw;
    if (target.height !== dh) target.height = dh;
    const ctx = target.getContext("2d", { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(source, 0, 0, dw, dh);
    return [dw, dh, scale];
  }

  function ensureTrack(dw: number, dh: number) {
    if (bgr && trackWidth === dw && trackHeight === dh) return;
    bgr?.delete();
    bgr = new cv.Mat(dh, dw, cv.CV_8UC3);
    detector.setInputSize(new cv.Size(dw, dh));
    trackWidth = dw;
    trackHeight = dh;
  }

  function embedOnBgr(mat: { delete?: () => void }, landmarks: number[][]): number[] {
    const aligned = new cv.Mat();
    const face112 = new cv.Size(112, 112);
    let transform: { delete: () => void } | null = null;
    try {
      const warp = sfaceWarpMatrix(landmarks);
      if (warp) {
        transform = cv.matFromArray(2, 3, cv.CV_32F, warp);
        cv.warpAffine(mat, aligned, transform, face112);
      } else {
        return [];
      }
      const blob = cv.blobFromImage(aligned, 1, face112, new cv.Scalar(0, 0, 0, 0), true, false);
      recognizer.setInput(blob);
      const vec = recognizer.forward();
      const embedding = Array.from(vec.data32F as Float32Array);
      blob.delete();
      vec.delete();
      return embedding;
    } finally {
      transform?.delete();
      aligned.delete();
    }
  }

  function runDetect(source: ImageSource, withEmbedding: boolean): WireFace[] {
    const size = sourceSize(source);
    if (!size) return [];
    const [width, height] = size;
    const drawn = drawScaled(canvas, source, withEmbedding ? EMBED_LONG_EDGE : TRACK_LONG_EDGE);
    if (!drawn) return [];
    const [dw, dh, scale] = drawn;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return [];
    ensureTrack(dw, dh);
    if (!bgr) return [];
    const fresh = cv.imread(canvas);
    try {
      cv.cvtColor(fresh, bgr, cv.COLOR_RGBA2BGR);
    } finally {
      fresh.delete();
    }
    if (!out) out = new cv.Mat();
    const detected = out;
    if (!detected) return [];
    detector.detect(bgr, detected);
    const inv = scale > 0 ? 1 / scale : 1;

    const faces: WireFace[] = [];
    const data = detected.data32F as Float32Array;
    for (let i = 0; i + 15 <= data.length; i += 15) {
      const x = Math.max(0, Math.round(data[i]));
      const y = Math.max(0, Math.round(data[i + 1]));
      const w = Math.round(data[i + 2]);
      const h = Math.round(data[i + 3]);
      if (w <= 1 || h <= 1) continue;
      const localMarks: number[][] = [];
      for (let k = 0; k < 5; k++) localMarks.push([data[i + 4 + 2 * k], data[i + 5 + 2 * k]]);
      const embedding = withEmbedding ? embedOnBgr(bgr, localMarks) : [];
      faces.push({
        embedding,
        landmarks: localMarks.map(([lx, ly]) => [lx * inv, ly * inv]),
        bbox: [Math.round(x * inv), Math.round(y * inv), Math.round(w * inv), Math.round(h * inv)],
        frame_size: [width, height],
      });
    }
    return faces;
  }

  function embedAt(source: ImageSource, landmarks: number[][]): number[] | null {
    const size = sourceSize(source);
    if (!size || landmarks.length < 5) return null;
    const drawn = drawScaled(embedCanvas, source, EMBED_LONG_EDGE);
    if (!drawn) return null;
    const [, , scale] = drawn;
    const rgbaE = cv.imread(embedCanvas);
    const bgrE = new cv.Mat();
    try {
      cv.cvtColor(rgbaE, bgrE, cv.COLOR_RGBA2BGR);
      const local = landmarks.slice(0, 5).map(([x, y]) => [x * scale, y * scale]);
      const embedding = embedOnBgr(bgrE, local);
      return embedding.length ? embedding : null;
    } finally {
      rgbaE.delete();
      bgrE.delete();
    }
  }

  function detectAndEmbed(source: ImageSource): WireFace[] {
    return runDetect(source, true);
  }

  function detect(source: ImageSource): WireFace[] {
    return runDetect(source, false);
  }

  function dispose(): void {
    for (const handle of [detector, recognizer, bgr, out]) {
      try {
        handle?.delete?.();
      } catch {
        /* best-effort */
      }
    }
    bgr = null;
    out = null;
  }

  return { detectAndEmbed, detect, embedAt, dispose };
}

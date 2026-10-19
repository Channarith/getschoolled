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
import { ModelLoadError, OPENCV_JS_URL, waitForCvRuntime } from "./opencvRuntime";
import { fetchVisionModel } from "./visionModels";

const DETECTOR_NAME = "face_detection_yunet_2023mar.onnx";
const RECOGNIZER_NAME = "face_recognition_sface_2021dec.onnx";
// YuNet's detection threshold; matches the server engine default.
const DET_SCORE_THRESHOLD = 0.7;

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

  /**
   * Core detect helper. If `withEmbedding` is false we skip the SFace
   * forward pass entirely — the single biggest CPU cost. Shared between
   * {@link detect} (fast landmarks-only) and {@link detectAndEmbed}
   * (slow full capture).
   */
  function runDetect(source: ImageSource, withEmbedding: boolean): WireFace[] {
    // Draw the source onto a canvas so OpenCV can read RGBA pixels.
    const width =
      (source as HTMLVideoElement).videoWidth ||
      (source as HTMLImageElement).naturalWidth ||
      (source as HTMLCanvasElement).width;
    const height =
      (source as HTMLVideoElement).videoHeight ||
      (source as HTMLImageElement).naturalHeight ||
      (source as HTMLCanvasElement).height;
    if (!width || !height) return [];

    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return [];
    ctx.drawImage(source, 0, 0, width, height);

    const rgba = cv.imread(canvas); // CV_8UC4
    const bgr = new cv.Mat();
    cv.cvtColor(rgba, bgr, cv.COLOR_RGBA2BGR);

    const out = new cv.Mat();
    detector.setInputSize(new cv.Size(width, height));
    detector.detect(bgr, out);

    const faces: WireFace[] = [];
    // Each detection row is 15 floats: x, y, w, h, then 5 (x,y) landmarks,
    // then the detection score.
    const data = out.data32F as Float32Array;
    for (let i = 0; i + 15 <= data.length; i += 15) {
      const x = Math.max(0, Math.round(data[i]));
      const y = Math.max(0, Math.round(data[i + 1]));
      const w = Math.round(data[i + 2]);
      const h = Math.round(data[i + 3]);
      if (w <= 0 || h <= 0) continue;
      const rw = Math.min(w, width - x);
      const rh = Math.min(h, height - y);
      if (rw <= 0 || rh <= 0) continue;

      let embedding: number[] = [];
      if (withEmbedding) {
        const rect = new cv.Rect(x, y, rw, rh);
        const roi = bgr.roi(rect);
        const blob = cv.blobFromImage(
          roi,
          1.0,
          new cv.Size(112, 112),
          new cv.Scalar(0, 0, 0, 0),
          true,
          false
        );
        recognizer.setInput(blob);
        const vec = recognizer.forward();
        embedding = Array.from(vec.data32F as Float32Array);
        blob.delete();
        vec.delete();
        roi.delete();
      }

      const landmarks: number[][] = [];
      for (let k = 0; k < 5; k++) {
        landmarks.push([data[i + 4 + 2 * k], data[i + 5 + 2 * k]]);
      }

      faces.push({
        embedding,
        landmarks,
        bbox: [x, y, w, h],
        frame_size: [width, height],
      });
    }

    rgba.delete();
    bgr.delete();
    out.delete();
    return faces;
  }

  function detectAndEmbed(source: ImageSource): WireFace[] {
    return runDetect(source, true);
  }

  function detect(source: ImageSource): WireFace[] {
    return runDetect(source, false);
  }

  function dispose(): void {
    for (const handle of [detector, recognizer]) {
      try {
        handle.delete?.();
      } catch {
        /* best-effort */
      }
    }
  }

  return { detectAndEmbed, detect, dispose };
}

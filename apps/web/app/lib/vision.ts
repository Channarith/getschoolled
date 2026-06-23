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

// OpenCV.js with FaceDetectorYN ships in the official 4.10.0+ build. Override
// with NEXT_PUBLIC_OPENCV_JS_URL to self-host the asset from your own origin.
const OPENCV_JS_URL =
  process.env.NEXT_PUBLIC_OPENCV_JS_URL ?? "https://docs.opencv.org/4.10.0/opencv.js";

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
  /** Free native (WASM) handles. */
  dispose: () => void;
};

let _cvReady: Promise<any> | null = null;

function loadOpenCv(): Promise<any> {
  if (_cvReady) return _cvReady;
  _cvReady = new Promise<any>((resolve, reject) => {
    const w = window as any;
    if (w.cv && w.cv.Mat) {
      resolve(w.cv);
      return;
    }
    const script = document.createElement("script");
    script.src = OPENCV_JS_URL;
    script.async = true;
    script.onload = () => {
      const cv = w.cv;
      if (!cv) {
        reject(new Error("opencv.js loaded but window.cv is undefined"));
        return;
      }
      // OpenCV.js may already be initialised, expose a Promise, or call
      // onRuntimeInitialized once the WASM runtime is ready.
      if (typeof cv.then === "function") {
        cv.then((ready: any) => resolve(ready)).catch(reject);
      } else if (cv.Mat) {
        resolve(cv);
      } else {
        cv.onRuntimeInitialized = () => resolve(cv);
      }
    };
    script.onerror = () =>
      reject(new Error(`failed to load opencv.js from ${OPENCV_JS_URL}`));
    document.body.appendChild(script);
  });
  return _cvReady;
}

async function stageModel(cv: any, name: string): Promise<void> {
  // Already staged into the Emscripten FS?
  try {
    cv.FS_stat?.("/" + name);
    return;
  } catch {
    /* not present yet */
  }
  const res = await fetch(visionModelUrl(name), { cache: "force-cache" });
  if (!res.ok) {
    throw new Error(`could not fetch model ${name}: ${res.status}`);
  }
  const buf = new Uint8Array(await res.arrayBuffer());
  cv.FS_createDataFile("/", name, buf, true, false, false);
}

/** Load OpenCV.js + the YuNet/SFace models and return a ready engine. */
export async function createVisionEngine(): Promise<VisionEngine> {
  const cv = await loadOpenCv();
  if (!cv.FaceDetectorYN) {
    throw new Error(
      "This OpenCV.js build lacks FaceDetectorYN; use the official 4.10.0+ build."
    );
  }
  await stageModel(cv, DETECTOR_NAME);
  await stageModel(cv, RECOGNIZER_NAME);

  const detector = new cv.FaceDetectorYN(
    DETECTOR_NAME,
    "",
    new cv.Size(320, 320),
    DET_SCORE_THRESHOLD,
    0.3,
    5000
  );
  const recognizer = cv.readNet(RECOGNIZER_NAME);

  function detectAndEmbed(source: ImageSource): WireFace[] {
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

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
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
      const embedding = Array.from(vec.data32F as Float32Array);

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

      blob.delete();
      vec.delete();
      roi.delete();
    }

    rgba.delete();
    bgr.delete();
    out.delete();
    return faces;
  }

  function dispose(): void {
    try {
      detector.delete?.();
    } catch {
      /* best-effort */
    }
  }

  return { detectAndEmbed, dispose };
}

import type { Point } from "./learnerCheck";

/**
 * On-device face read for Learner Check.
 * Google ML Kit runs on the phone. Identity is not contacted for the live lines.
 * The five landmarks follow YuNet order: right eye, left eye, nose, right mouth, left mouth.
 * The strokes are the real face outline, eyes, brows, nose, and lips.
 */

export type DeviceStroke = { points: Point[]; closed: boolean };

export type DeviceFaceRead = {
  landmarks: number[][] | null;
  bbox: number[];
  strokes: DeviceStroke[];
  smiling: number | null;
  faceWidth: number;
};

type MlPoint = { x?: number; y?: number };
type MlFace = {
  frame?: { left?: number; top?: number; width?: number; height?: number };
  landmarks?: Record<string, { position?: MlPoint } | undefined>;
  contours?: Record<string, { points?: MlPoint[] | null } | undefined>;
  smilingProbability?: number;
};

const CLOSED = new Set([
  "face",
  "leftEye",
  "rightEye",
  "upperLipTop",
  "upperLipBottom",
  "lowerLipTop",
  "lowerLipBottom",
]);

const STROKE_ORDER = [
  "face",
  "leftEyebrowTop",
  "leftEyebrowBottom",
  "rightEyebrowTop",
  "rightEyebrowBottom",
  "leftEye",
  "rightEye",
  "noseBridge",
  "noseBottom",
  "upperLipTop",
  "upperLipBottom",
  "lowerLipTop",
  "lowerLipBottom",
];

function point(value: MlPoint | undefined): Point | null {
  const x = Number(value?.x);
  const y = Number(value?.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

/** How the face fills the still. The long side of the photo is the span. */
export function faceDistanceCue(faceWidth: number, frameSpan: number): "closer" | "back" | "ok" {
  if (!(faceWidth > 0) || !(frameSpan > 0)) return "ok";
  const ratio = faceWidth / frameSpan;
  if (ratio < 0.16) return "closer";
  if (ratio > 0.62) return "back";
  return "ok";
}

export function isOnDeviceReaderMissing(reason: unknown): boolean {
  const message = String((reason as Error)?.message ?? reason ?? "");
  return /doesn't seem to be linked|does not seem to be linked|not in this build|rebuild the app/i.test(message);
}

export function readMlKitFace(face: MlFace | null | undefined): DeviceFaceRead | null {
  if (!face?.frame) return null;
  const left = Number(face.frame.left);
  const top = Number(face.frame.top);
  const width = Number(face.frame.width);
  const height = Number(face.frame.height);
  if (![left, top, width, height].every((n) => Number.isFinite(n)) || width < 2 || height < 2) return null;
  const landmarks = ["rightEye", "leftEye", "noseBase", "mouthRight", "mouthLeft"].map((key) => (
    point(face.landmarks?.[key]?.position)
  ));
  const strokes: DeviceStroke[] = [];
  for (const key of STROKE_ORDER) {
    const raw = face.contours?.[key]?.points;
    if (!raw?.length) continue;
    const points = raw.map((item) => point(item)).filter((item): item is Point => item != null);
    if (points.length < 2) continue;
    strokes.push({ points, closed: CLOSED.has(key) });
  }
  const smiling = Number(face.smilingProbability);
  return {
    landmarks: landmarks.every((item) => item) ? landmarks.map((item) => [item![0], item![1]]) : null,
    bbox: [left, top, width, height],
    strokes,
    smiling: Number.isFinite(smiling) ? smiling : null,
    faceWidth: width,
  };
}

type FaceDetectionModule = {
  detect: (imageURL: string, options?: Record<string, unknown>) => Promise<MlFace[]>;
};

/**
 * Read every face in a still that is already on this phone.
 * The native module is loaded only when a frame is ready, so a JS test bundle
 * does not crash when the binary has not been rebuilt yet.
 */
export async function detectDeviceFaces(uri: string): Promise<DeviceFaceRead[]> {
  let detect: FaceDetectionModule["detect"] | undefined;
  try {
    const loaded = require("@react-native-ml-kit/face-detection") as { default?: FaceDetectionModule } & FaceDetectionModule;
    detect = loaded.default?.detect ?? loaded.detect;
  } catch (reason) {
    throw Object.assign(
      new Error("The on-device face reader is not in this build. Rebuild the app and try again."),
      { cause: reason },
    );
  }
  if (typeof detect !== "function") {
    throw new Error("The on-device face reader is not in this build. Rebuild the app and try again.");
  }
  const faces = await detect(uri, {
    performanceMode: "fast",
    landmarkMode: "all",
    contourMode: "all",
    classificationMode: "all",
    minFaceSize: 0.08,
  });
  return (faces ?? []).map((face) => readMlKitFace(face)).filter((face): face is DeviceFaceRead => face != null);
}

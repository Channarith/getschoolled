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
  /** Head turn left or right, in degrees. 0 is straight at the camera. */
  yaw: number | null;
  /** Head tilt up or down, in degrees. */
  pitch: number | null;
  /** Lower of the two open-eye scores, 0 to 1. Null when the phone did not score it. */
  eyesOpen: number | null;
};

type MlPoint = { x?: number; y?: number };
type MlFace = {
  frame?: { left?: number; top?: number; width?: number; height?: number };
  landmarks?: Record<string, { position?: MlPoint } | undefined>;
  contours?: Record<string, { points?: MlPoint[] | null } | undefined>;
  smilingProbability?: number;
  rotationX?: number;
  rotationY?: number;
  leftEyeOpenProbability?: number;
  rightEyeOpenProbability?: number;
};

function finite(value: unknown): number | null {
  const n = Number(value);
  return value != null && Number.isFinite(n) ? n : null;
}

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
  const leftEye = finite(face.leftEyeOpenProbability);
  const rightEye = finite(face.rightEyeOpenProbability);
  return {
    landmarks: landmarks.every((item) => item) ? landmarks.map((item) => [item![0], item![1]]) : null,
    bbox: [left, top, width, height],
    strokes,
    smiling: finite(face.smilingProbability),
    faceWidth: width,
    yaw: finite(face.rotationY),
    pitch: finite(face.rotationX),
    eyesOpen: leftEye == null && rightEye == null ? null : Math.min(leftEye ?? 1, rightEye ?? 1),
  };
}

export type FrameVerdict = "ok" | "none" | "many" | "closer" | "back" | "center" | "straight" | "eyes";

/** Head turn or tilt we still count as looking at the camera. */
export const STRAIGHT_DEGREES = 18;

/**
 * Whether one still is good enough to keep for the face check.
 * The learner only has to look at the camera: one face, centered, at a
 * comfortable distance, roughly straight on, eyes open.
 */
export function frameVerdict(faces: DeviceFaceRead[], frame: [number, number]): FrameVerdict {
  if (faces.length === 0) return "none";
  const big = faces.filter((face) => face.faceWidth >= faces[0].faceWidth * 0.5);
  if (faces.length > 1 && big.length > 1) return "many";
  const face = faces.reduce((a, b) => (b.faceWidth > a.faceWidth ? b : a));
  const [width, height] = frame;
  const cue = faceDistanceCue(face.faceWidth, Math.max(width, height));
  if (cue !== "ok") return cue;
  const [left, top, boxWidth, boxHeight] = face.bbox;
  const dx = Math.abs(left + boxWidth / 2 - width / 2) / width;
  const dy = Math.abs(top + boxHeight / 2 - height / 2) / height;
  if (dx > 0.2 || dy > 0.22) return "center";
  if (Math.abs(face.yaw ?? 0) > STRAIGHT_DEGREES || Math.abs(face.pitch ?? 0) > STRAIGHT_DEGREES) return "straight";
  if (face.eyesOpen != null && face.eyesOpen < 0.35) return "eyes";
  return "ok";
}

export const FRAME_HINT: Record<Exclude<FrameVerdict, "ok">, string> = {
  none: "Look at the camera.",
  many: "Only one face, please.",
  closer: "Move a little closer.",
  back: "Move back a little.",
  center: "Center your face in the circle.",
  straight: "Look straight at the camera.",
  eyes: "Keep your eyes open.",
};

type FaceDetectionModule = {
  detect: (imageURL: string, options?: Record<string, unknown>) => Promise<MlFace[]>;
};

/**
 * Read every face in a still that is already on this phone.
 * The native module is loaded only when a frame is ready, so a JS test bundle
 * does not crash when the binary has not been rebuilt yet.
 */
export async function detectDeviceFaces(
  uri: string,
  { contours = true }: { contours?: boolean } = {},
): Promise<DeviceFaceRead[]> {
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
    landmarkMode: contours ? "all" : "none",
    contourMode: contours ? "all" : "none",
    classificationMode: "all",
    minFaceSize: contours ? 0.08 : 0.12,
  });
  return (faces ?? []).map((face) => readMlKitFace(face)).filter((face): face is DeviceFaceRead => face != null);
}

import { withTimeout, type Point } from "./learnerCheck";

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
  /** Head tilt in the picture plane (the Z axis), in degrees. 0 is level. */
  roll: number | null;
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
  if (ratio < 0.13) return "closer";
  if (ratio > 0.62) return "back";
  return "ok";
}

export function isOnDeviceReaderMissing(reason: unknown): boolean {
  const message = String((reason as Error)?.message ?? reason ?? "");
  return /doesn't seem to be linked|does not seem to be linked|not in this build|rebuild the app/i.test(message);
}

/** Head tilt from the eye line (right eye first). Null without both eyes. */
export function rollFromLandmarks(landmarks: number[][] | null): number | null {
  if (!landmarks || landmarks.length < 2) return null;
  const [right, left] = landmarks;
  if (!right || !left || (right[0] === left[0] && right[1] === left[1])) return null;
  let angle = (Math.atan2(left[1] - right[1], left[0] - right[0]) * 180) / Math.PI;
  if (angle > 90) angle -= 180;
  else if (angle < -90) angle += 180;
  return angle;
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
  const marks = landmarks.every((item) => item) ? landmarks.map((item) => [item![0], item![1]]) : null;
  return {
    landmarks: marks,
    bbox: [left, top, width, height],
    strokes,
    smiling: finite(face.smilingProbability),
    faceWidth: width,
    yaw: finite(face.rotationY),
    pitch: finite(face.rotationX),
    eyesOpen: leftEye == null && rightEye == null ? null : Math.min(leftEye ?? 1, rightEye ?? 1),
    roll: finite((face as { rotationZ?: number }).rotationZ) ?? rollFromLandmarks(marks),
  };
}

export type FrameVerdict = "ok" | "none" | "many" | "closer" | "back" | "center" | "straight" | "tilt" | "eyes";

/** Head turn or tilt we still count as looking at the camera. */
export const STRAIGHT_DEGREES = 24;
/** Sideways head tilt (Z axis) we still keep. The server levels small tilts; large ones lose the face. */
export const ROLL_DEGREES = 30;
/** Share of the picture kept clear at each edge so the whole face is in view. */
export const FRAME_MARGIN = 0.02;

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
  // The face does not have to sit inside the on-screen oval, only be whole in
  // the picture: a face cut off by the edge cannot give a full outline.
  const [left, top, boxWidth, boxHeight] = face.bbox;
  if (
    left < width * FRAME_MARGIN || top < height * FRAME_MARGIN
    || left + boxWidth > width * (1 - FRAME_MARGIN) || top + boxHeight > height * (1 - FRAME_MARGIN)
  ) return "center";
  if (Math.abs(face.yaw ?? 0) > STRAIGHT_DEGREES || Math.abs(face.pitch ?? 0) > STRAIGHT_DEGREES) return "straight";
  if (face.roll != null && Math.abs(face.roll) > ROLL_DEGREES) return "tilt";
  if (face.eyesOpen != null && face.eyesOpen < 0.25) return "eyes";
  return "ok";
}

/**
 * The size of the picture the face boxes are measured in. iOS can report the
 * sensor's landscape size for a still that is stored sideways, while ML Kit
 * measures the face in the upright picture; every box then looks off-centre.
 * When the boxes cannot fit the reported size but fit it turned, use the
 * turned size.
 */
export function frameForFaces(frame: [number, number], faces: DeviceFaceRead[]): [number, number] {
  const [width, height] = frame;
  if (!faces.length || !(width > 0) || !(height > 0)) return frame;
  const fits = (w: number, h: number) => faces.every((face) => {
    const [left, top, boxWidth, boxHeight] = face.bbox;
    return left >= -w * 0.05 && top >= -h * 0.05 && left + boxWidth <= w * 1.05 && top + boxHeight <= h * 1.05;
  });
  if (fits(width, height)) return frame;
  if (fits(height, width)) return [height, width];
  return frame;
}

export type ScanStats = {
  grabbed: number;
  grabMissed: number;
  faceFrames: number;
  emptyFrames: number;
  readFailures: number;
  size: [number, number] | null;
  upright: [number, number] | null;
  lastGrabError: string;
  lastReadError: string;
};

/** One short line for the failure card, so a screenshot says what the phone saw. */
export function scanDiagnostics(stats: ScanStats, counts: VerdictCounts): string {
  const verdicts = Object.entries(counts).map(([name, n]) => `${name} ${n}`).join(", ") || "none";
  const dims = (d: [number, number] | null) => (d ? `${d[0]}x${d[1]}` : "?");
  const parts = [
    `pictures ${stats.grabbed} ok / ${stats.grabMissed} missed`,
    `faces found in ${stats.faceFrames}, none in ${stats.emptyFrames}`,
    `size ${dims(stats.size)}, upright ${dims(stats.upright)}`,
    `verdicts: ${verdicts}`,
  ];
  if (stats.readFailures) parts.push(`reader errors ${stats.readFailures}`);
  if (stats.lastGrabError) parts.push(`camera: ${stats.lastGrabError.slice(0, 80)}`);
  if (stats.lastReadError) parts.push(`reader: ${stats.lastReadError.slice(0, 80)}`);
  return parts.join(" · ");
}

export type VerdictCounts = Partial<Record<FrameVerdict, number>>;

const FAILURE_MESSAGE: Record<Exclude<FrameVerdict, "ok" | "none">, string> = {
  many: "We saw more than one face. Make sure only you are in the picture, then try again.",
  closer: "You looked too far from the camera. Bring the phone a little closer, then try again.",
  back: "You looked too close to the camera. Move the phone back a little, then try again.",
  center: "Part of your face was cut off by the edge of the picture. Hold the phone at eye level so your whole face is in view, then try again.",
  straight: "We need you looking straight at the camera. Hold the phone at eye level, then try again.",
  tilt: "Your head was tilted to the side. Keep it level and try again.",
  eyes: "We couldn’t see your eyes clearly. Face a light, keep your eyes open and look at the camera, then try again.",
};

/** What to tell the learner when no five frames passed, from what the phone actually saw. */
export function scanFailureMessage(counts: VerdictCounts): string {
  let top: FrameVerdict = "none";
  let best = 0;
  for (const [verdict, count] of Object.entries(counts) as [FrameVerdict, number][]) {
    if (verdict !== "ok" && count > best) {
      top = verdict;
      best = count;
    }
  }
  if (top === "none") {
    return "We couldn’t get a clear look. Face a window or lamp, hold the phone at eye level, and try again.";
  }
  return FAILURE_MESSAGE[top];
}

/** Most stills kept for one face check. The best five are used; the server may pick among all of them. */
export const FACE_CANDIDATES = 6;

export type FaceBox = { cx: number; cy: number; width: number };

export function faceBox(face: DeviceFaceRead): FaceBox {
  const [left, top, width, height] = face.bbox;
  return { cx: left + width / 2, cy: top + height / 2, width };
}

/** The face moved more than a fifth of its width since the last still, so this one is likely smeared. */
export function movedTooMuch(previous: FaceBox | null, now: FaceBox): boolean {
  if (!previous) return false;
  const shift = Math.hypot(now.cx - previous.cx, now.cy - previous.cy);
  return shift > 0.2 * Math.max(previous.width, now.width);
}

/**
 * A blurred still compresses smaller than a sharp one at the same JPEG quality.
 * Compare against the largest recent still; no sharpness metric is available here.
 */
export function looksBlurred(length: number, recentLengths: number[]): boolean {
  if (recentLengths.length < 2) return false;
  return length < 0.55 * Math.max(...recentLengths);
}

/** Higher is a better reference photo: level, frontal, eyes open, centered, detailed. */
export function stillScore(face: DeviceFaceRead, frame: [number, number], length: number, largest: number): number {
  const turn = (Math.abs(face.yaw ?? 0) + Math.abs(face.pitch ?? 0)) / (2 * STRAIGHT_DEGREES);
  const tilt = Math.abs(face.roll ?? 0) / ROLL_DEGREES;
  const [left, top, width, height] = face.bbox;
  const off = Math.hypot((left + width / 2) / frame[0] - 0.5, (top + height / 2) / frame[1] - 0.5);
  const detail = largest > 0 ? Math.min(1, length / largest) : 1;
  return 1 - 0.5 * turn - 0.3 * tilt + 0.3 * (face.eyesOpen ?? 1) + 0.4 * detail - 0.5 * off;
}

export type ScoredStill = { base64: string; score: number };

/** Best first. The first one is the reference the others are compared with. */
export function rankStills(stills: ScoredStill[]): string[] {
  return [...stills].sort((a, b) => b.score - a.score).map((still) => still.base64);
}

export const FRAME_HINT: Record<Exclude<FrameVerdict, "ok">, string> = {
  none: "Look at the camera.",
  many: "Only one face, please.",
  closer: "Move a little closer.",
  back: "Move back a little.",
  center: "Keep your whole face in view.",
  straight: "Look straight at the camera.",
  tilt: "Keep your head level.",
  eyes: "Keep your eyes open.",
};

/** One read of a still should take well under a second; do not wait forever on a stuck one. */
export const DETECT_TIMEOUT_MS = 6000;

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
  { contours = true, accurate = false }: { contours?: boolean; accurate?: boolean } = {},
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
  // The accurate pass is the fallback when the fast one keeps finding nothing:
  // no outline, a smaller minimum face, the slower detector.
  const faces = await withTimeout(detect(uri, accurate ? {
    performanceMode: "accurate",
    landmarkMode: "none",
    contourMode: "none",
    classificationMode: "all",
    minFaceSize: 0.05,
  } : {
    performanceMode: "fast",
    landmarkMode: contours ? "all" : "none",
    contourMode: contours ? "all" : "none",
    classificationMode: "all",
    minFaceSize: contours ? 0.08 : 0.12,
  }), accurate ? DETECT_TIMEOUT_MS * 2 : DETECT_TIMEOUT_MS, "The on-device face reader took too long.");
  return (faces ?? []).map((face) => readMlKitFace(face)).filter((face): face is DeviceFaceRead => face != null);
}

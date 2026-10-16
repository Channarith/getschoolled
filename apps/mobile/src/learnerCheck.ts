// Pure helpers for the Salareen Learner Check, mirrored from
// apps/web/app/lib/learnerCheck.ts so web and native draw the same contour and
// waveform.

export type Point = [number, number];
export type Pose = "left" | "right" | "up" | "down";
export const POSES: Pose[] = ["left", "right", "up", "down"];

export const AGE_MIN = 3;
export const AGE_MAX = 120;
export const AGE_OPTIONS: number[] = Array.from({ length: AGE_MAX - AGE_MIN + 1 }, (_, i) => AGE_MIN + i);

export function clampAge(value: number): number {
  return Math.min(AGE_MAX, Math.max(AGE_MIN, Math.round(value)));
}

/** A fresh random order of the four look-targets. */
export function shuffledPoses(random: () => number = Math.random): Pose[] {
  const order = [...POSES];
  for (let i = order.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return order;
}

export type Geometry = { yaw: number; pitch: number; centered: boolean };

function finitePoints(landmarks: number[][] | undefined | null): Point[] | null {
  if (!landmarks || landmarks.length < 5) return null;
  const points = landmarks.slice(0, 5).map((p) => [Number(p[0]), Number(p[1])] as Point);
  return points.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y)) ? points : null;
}

/** Head yaw/pitch from YuNet's 5 landmarks (right eye, left eye, nose, right and left mouth corner). */
export function faceGeometry(landmarks: number[][], bbox: number[], frame: number[]): Geometry | null {
  const points = finitePoints(landmarks);
  if (!points) return null;
  const [rightEye, leftEye, nose, rightMouth, leftMouth] = points;
  const eyeMid = [(rightEye[0] + leftEye[0]) / 2, (rightEye[1] + leftEye[1]) / 2];
  const mouthMid = [(rightMouth[0] + leftMouth[0]) / 2, (rightMouth[1] + leftMouth[1]) / 2];
  const eyeDist = Math.hypot(leftEye[0] - rightEye[0], leftEye[1] - rightEye[1]);
  const faceHeight = mouthMid[1] - eyeMid[1];
  if (eyeDist <= 1 || faceHeight <= 1) return null;
  const axisX = (eyeMid[0] + mouthMid[0]) / 2;
  const cx = bbox[0] + bbox[2] / 2;
  const cy = bbox[1] + bbox[3] / 2;
  return {
    yaw: (nose[0] - axisX) / eyeDist,
    pitch: (nose[1] - eyeMid[1]) / faceHeight,
    centered: Math.abs(cx / frame[0] - 0.5) < 0.2 && Math.abs(cy / frame[1] - 0.5) < 0.22,
  };
}

// Normalized nose offset that counts as a deliberate head turn.
export const YAW_THRESHOLD = 0.16;
export const PITCH_THRESHOLD = 0.1;

/**
 * Which way the learner is looking relative to their neutral pose, in the
 * mirrored preview the learner sees. Null while the head is still near neutral.
 */
export function poseFromBaseline(base: Geometry, now: Geometry, mirrored = true): Pose | null {
  const dx = (mirrored ? -1 : 1) * (now.yaw - base.yaw) / YAW_THRESHOLD;
  const dy = (now.pitch - base.pitch) / PITCH_THRESHOLD;
  if (Math.hypot(dx, dy) < 1) return null;
  if (Math.abs(dx) >= Math.abs(dy)) return dx < 0 ? "left" : "right";
  return dy < 0 ? "up" : "down";
}

export type FaceContour = {
  outline: Point[];
  rightEye: Point[];
  leftEye: Point[];
  nose: Point[];
  mouth: Point[];
};

/**
 * Estimate a face contour from the 5 landmarks: a jaw and cheek outline that
 * follows the eye line and mouth, plus eye, nose, and mouth strokes. Returns
 * null when the landmarks are missing or degenerate so callers hide the overlay
 * instead of drawing a stale shape.
 */
export function faceContour(landmarks: number[][] | undefined | null, samples = 32): FaceContour | null {
  const points = finitePoints(landmarks);
  if (!points) return null;
  const [rightEye, leftEye, nose, rightMouth, leftMouth] = points;
  const eyeDist = Math.hypot(leftEye[0] - rightEye[0], leftEye[1] - rightEye[1]);
  if (eyeDist <= 1) return null;
  const u: Point = [(leftEye[0] - rightEye[0]) / eyeDist, (leftEye[1] - rightEye[1]) / eyeDist];
  let v: Point = [-u[1], u[0]];
  const eyeMid: Point = [(rightEye[0] + leftEye[0]) / 2, (rightEye[1] + leftEye[1]) / 2];
  const mouthMid: Point = [(rightMouth[0] + leftMouth[0]) / 2, (rightMouth[1] + leftMouth[1]) / 2];
  const down = (mouthMid[0] - eyeMid[0]) * v[0] + (mouthMid[1] - eyeMid[1]) * v[1];
  if (down < 0) v = [-v[0], -v[1]];
  const height = Math.abs(down);
  if (height <= 1) return null;
  const at = (origin: Point, a: number, b: number): Point => [
    origin[0] + u[0] * a + v[0] * b,
    origin[1] + u[1] * a + v[1] * b,
  ];
  // Turning the head moves the nose off the eye-mouth axis; lean the outline with it.
  const axis: Point = [(eyeMid[0] + mouthMid[0]) / 2, (eyeMid[1] + mouthMid[1]) / 2];
  const lean = ((nose[0] - axis[0]) * u[0] + (nose[1] - axis[1]) * u[1]) * 0.45;
  const center = at(eyeMid, lean, height * 0.42);
  const halfWidth = eyeDist * 1.02;
  const top = height * 1.75;
  const bottom = height * 1.32;
  const outline: Point[] = [];
  for (let i = 0; i < samples; i += 1) {
    const t = (i / samples) * Math.PI * 2;
    const s = Math.sin(t);
    const jaw = s > 0 ? 1 - 0.22 * s * s : 1;
    outline.push(at(center, Math.cos(t) * halfWidth * jaw, s * (s > 0 ? bottom : top)));
  }
  const eye = (c: Point): Point[] => {
    const w = eyeDist * 0.2;
    const h = eyeDist * 0.075;
    return [at(c, -w, 0), at(c, -w * 0.5, -h), at(c, w * 0.5, -h), at(c, w, 0), at(c, w * 0.5, h), at(c, -w * 0.5, h)];
  };
  const noseStroke: Point[] = [
    at(eyeMid, 0, height * 0.12),
    nose,
    at(nose, -eyeDist * 0.16, height * 0.12),
    at(nose, eyeDist * 0.16, height * 0.12),
    nose,
  ];
  const mouth: Point[] = [
    rightMouth,
    at(mouthMid, 0, -height * 0.06),
    leftMouth,
    at(mouthMid, 0, height * 0.14),
  ];
  return { outline, rightEye: eye(rightEye), leftEye: eye(leftEye), nose: noseStroke, mouth };
}

/** SVG path data for a polyline; closed paths end with Z. */
export function svgPath(points: Point[], closed = false): string {
  if (!points.length) return "";
  const body = points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return closed ? `${body} Z` : body;
}

export type LevelSample = { t: number; level: number };

/**
 * Bar heights (0..1) for the linear voice waveform. Bar i covers
 * [i, i+1) * duration / bars seconds; bars past the latest sample stay 0 so the
 * row fills left to right as the recording runs.
 */
export function waveformBars(samples: LevelSample[], durationS: number, bars: number): number[] {
  const heights = Array<number>(bars).fill(0);
  if (bars <= 0 || durationS <= 0) return heights;
  const slot = durationS / bars;
  for (const { t, level } of samples) {
    if (t < 0 || t >= durationS) continue;
    const index = Math.min(bars - 1, Math.floor(t / slot));
    heights[index] = Math.max(heights[index], Math.min(1, Math.max(0, level)));
  }
  return heights;
}


/** expo-av metering is dBFS (about -160..0); map speech (-50..-5 dB) onto 0..1. */
export function meteringToLevel(db: number | undefined | null): number {
  if (db == null || !Number.isFinite(db)) return 0;
  return Math.min(1, Math.max(0, (db + 50) / 45));
}

/** The site palette (apps/web/app/globals.css) used by the setup assistant. */
export const SETUP_COLORS = {
  bg: "#f4e9d8",
  panel: "#ffffff",
  panel2: "#f3e9db",
  accent: "#2f6bd8",
  teal: "#0f9d8f",
  text: "#241b34",
  muted: "#736a82",
  border: "#e3d7c3",
  warm: "#fb923c",
  warmSoft: "#fff7ed",
  warmText: "#9a3412",
  danger: "#b42318",
  dangerSoft: "#fef2f2",
} as const;

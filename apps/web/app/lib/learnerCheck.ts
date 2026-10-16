// Pure geometry and signal helpers for the Salareen Learner Check (setup
// assistant). No DOM access here, so `npm run test:unit` can exercise them.

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

/**
 * Head yaw/pitch from YuNet's 5 landmarks (right eye, left eye, nose, right
 * and left mouth corner), measured in the face's own axes so a tilted head
 * does not turn a sideways look into up/down.
 *
 * Yaw is the nose offset from the eye midpoint along the eye line. Folding
 * the mouth into that axis cancelled the signal: the mouth shifts with the
 * nose, so a clear ~20° look stayed under 0.16 and never matched the prompt.
 * Pitch is how far the nose sits from the eyes toward the mouth. Looking up
 * moves the nose toward the eyes (smaller pitch).
 *
 * Positive yaw means the nose moved toward the person's left eye — the right
 * side of an unmirrored camera frame.
 */
export function faceGeometry(landmarks: number[][], bbox: number[], frame: number[]): Geometry | null {
  const points = finitePoints(landmarks);
  if (!points) return null;
  const [rightEye, leftEye, nose, rightMouth, leftMouth] = points;
  const eyeMid = [(rightEye[0] + leftEye[0]) / 2, (rightEye[1] + leftEye[1]) / 2];
  const mouthMid = [(rightMouth[0] + leftMouth[0]) / 2, (rightMouth[1] + leftMouth[1]) / 2];
  const eyeDist = Math.hypot(leftEye[0] - rightEye[0], leftEye[1] - rightEye[1]);
  if (eyeDist <= 1) return null;
  const u: Point = [(leftEye[0] - rightEye[0]) / eyeDist, (leftEye[1] - rightEye[1]) / eyeDist];
  let v: Point = [-u[1], u[0]];
  const down = (mouthMid[0] - eyeMid[0]) * v[0] + (mouthMid[1] - eyeMid[1]) * v[1];
  if (down < 0) v = [-v[0], -v[1]];
  const faceHeight = Math.abs(down);
  if (faceHeight <= 1) return null;
  const noseAlong = (nose[0] - eyeMid[0]) * u[0] + (nose[1] - eyeMid[1]) * u[1];
  const noseDown = (nose[0] - eyeMid[0]) * v[0] + (nose[1] - eyeMid[1]) * v[1];
  const cx = bbox[0] + bbox[2] / 2;
  const cy = bbox[1] + bbox[3] / 2;
  const frameW = frame[0] || 1;
  const frameH = frame[1] || 1;
  return {
    yaw: noseAlong / eyeDist,
    pitch: noseDown / faceHeight,
    centered: Math.abs(cx / frameW - 0.5) < 0.2 && Math.abs(cy / frameH - 0.5) < 0.22,
  };
}

// A deliberate look is about 12° of head rotation (~0.10 of the eye distance
// in yaw, ~0.07 in pitch). The old 0.16 / 0.10 gates needed ~25° / ~15° and a
// normal look stayed neutral. About 5° of sway stays under these.
export const YAW_THRESHOLD = 0.08;
export const PITCH_THRESHOLD = 0.05;

/**
 * Which way the learner is looking relative to their neutral pose.
 * Landmarks come from the raw camera frame. The setup preview is a mirror, so
 * mirrored yaw is flipped: turning to the learner's left (nose toward their
 * left eye) registers as "left", matching the prompted arrow.
 * Null while the head is still near neutral.
 */
export function poseFromBaseline(base: Geometry, now: Geometry, mirrored = true): Pose | null {
  const dx = (mirrored ? -1 : 1) * (now.yaw - base.yaw) / YAW_THRESHOLD;
  const dy = (now.pitch - base.pitch) / PITCH_THRESHOLD;
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  // The winning axis has to clear its own threshold. Combining two
  // sub-threshold axes labeled a sideways look as up or down whenever the
  // pitch component was slightly larger, so the prompted direction never matched.
  if (Math.max(ax, ay) < 1) return null;
  if (ax >= ay) return dx < 0 ? "left" : "right";
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

export type LightingAction = "none" | "torch" | "screen";

/** Average luma (0..1) of an RGBA buffer, sampling every `stride`th pixel. */
export function meanLuma(rgba: ArrayLike<number>, stride = 8): number {
  let total = 0;
  let count = 0;
  for (let i = 0; i + 2 < rgba.length; i += 4 * stride) {
    total += 0.2126 * rgba[i] + 0.7152 * rgba[i + 1] + 0.0722 * rgba[i + 2];
    count += 1;
  }
  return count ? total / count / 255 : 0;
}

export const DARK_LUMA = 0.24;

/** Too dark: use the camera torch when the device has one, else light the face with a white screen. */
export function lightingAction(luma: number, torchSupported: boolean): LightingAction {
  if (luma >= DARK_LUMA) return "none";
  return torchSupported ? "torch" : "screen";
}

/** Loudness (0..1) from an AnalyserNode time-domain buffer (unsigned bytes centred on 128). */
export function levelFromTimeDomain(bytes: ArrayLike<number>): number {
  if (!bytes.length) return 0;
  let sum = 0;
  for (let i = 0; i < bytes.length; i += 1) {
    const sample = (bytes[i] - 128) / 128;
    sum += sample * sample;
  }
  return Math.min(1, Math.sqrt(Math.sqrt(sum / bytes.length)) * 1.6);
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

/** First container this browser can record; "" lets MediaRecorder pick its default. */
export const RECORDER_MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

export function pickRecorderMime(isTypeSupported?: (type: string) => boolean): string {
  if (typeof isTypeSupported !== "function") return "";
  for (const type of RECORDER_MIME_CANDIDATES) {
    try {
      if (isTypeSupported(type)) return type;
    } catch {
      /* some engines throw for unknown types */
    }
  }
  return "";
}

export type MediaProblem = "permission" | "missing" | "busy" | "insecure" | "model" | "unsupported" | "unknown";

/** Turn getUserMedia / model failures into a cause the learner can act on. */
export function describeMediaError(reason: unknown, device: "camera" | "microphone"): { kind: MediaProblem; message: string } {
  const name = (reason as { name?: string } | null)?.name ?? "";
  const raw = String((reason as { message?: string } | null)?.message ?? reason ?? "");
  const Device = device === "camera" ? "Camera" : "Microphone";
  if (name === "ModelLoadError") {
    return { kind: "model", message: `Couldn’t load the face model. Check your connection and try again. (${raw})` };
  }
  if (name === "NotAllowedError" || name === "PermissionDeniedError" || name === "SecurityError") {
    return {
      kind: "permission",
      message: `${Device} access is blocked. Allow the ${device} for this site in your browser settings, then try again.`,
    };
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError" || name === "OverconstrainedError") {
    return { kind: "missing", message: `No ${device} was found on this device.` };
  }
  if (name === "NotReadableError" || name === "TrackStartError" || name === "AbortError") {
    return { kind: "busy", message: `Another app is using the ${device}. Close it and try again.` };
  }
  if (name === "NotSupportedError") {
    return { kind: "unsupported", message: `This browser can’t record from the ${device}. Try Chrome, Safari, or Edge.` };
  }
  if (/mediaDevices|getUserMedia|secure context/i.test(raw)) {
    return { kind: "insecure", message: `${Device} access needs a secure (https) page.` };
  }
  return { kind: "unknown", message: `${Device} unavailable: ${raw.replace(/^Error:\s*/, "")}` };
}

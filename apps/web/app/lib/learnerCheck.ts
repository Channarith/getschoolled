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

/** SFace's 112×112 canonical eyes, nose, and mouth corners (OpenCV FaceRecognizerSF). */
const SFACE_TEMPLATE: Point[] = [
  [38.2946, 51.6963],
  [73.5318, 51.5014],
  [56.0252, 71.7366],
  [41.5493, 92.3655],
  [70.7299, 92.2041],
];

/**
 * 2×3 similarity that warps YuNet's five landmarks onto the SFace template.
 * This is the browser stand-in for FaceRecognizerSF.alignCrop, which the
 * OpenCV.js build does not ship. A raw face-box crop leaves a turned head in
 * a different frame from the portrait, so their embeddings miss the pose check.
 * Returns [a, b, tx, c, d, ty] for x' = a x + b y + tx, y' = c x + d y + ty.
 */
export function sfaceWarpMatrix(landmarks: number[][] | undefined | null): number[] | null {
  const src = finitePoints(landmarks);
  if (!src) return null;
  let srcX = 0;
  let srcY = 0;
  let dstX = 0;
  let dstY = 0;
  for (let i = 0; i < 5; i += 1) {
    srcX += src[i][0];
    srcY += src[i][1];
    dstX += SFACE_TEMPLATE[i][0];
    dstY += SFACE_TEMPLATE[i][1];
  }
  srcX /= 5;
  srcY /= 5;
  dstX /= 5;
  dstY /= 5;
  let srcVar = 0;
  let align = 0;
  let turn = 0;
  for (let i = 0; i < 5; i += 1) {
    const sx = src[i][0] - srcX;
    const sy = src[i][1] - srcY;
    const dx = SFACE_TEMPLATE[i][0] - dstX;
    const dy = SFACE_TEMPLATE[i][1] - dstY;
    srcVar += sx * sx + sy * sy;
    align += dx * sx + dy * sy;
    turn += dy * sx - dx * sy;
  }
  srcVar /= 5;
  align /= 5;
  turn /= 5;
  if (srcVar < 1e-6) return null;
  const norm = Math.hypot(align, turn);
  if (norm < 1e-8) return null;
  const scale = norm / srcVar;
  const cos = align / norm;
  const sin = turn / norm;
  return [
    scale * cos,
    scale * -sin,
    dstX - scale * (cos * srcX - sin * srcY),
    scale * sin,
    scale * cos,
    dstY - scale * (sin * srcX + cos * srcY),
  ];
}

export function cosineSimilarity(a: number[] | undefined | null, b: number[] | undefined | null): number {
  if (!a?.length || !b || a.length !== b.length) return 0;
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i += 1) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb);
  return denom ? dot / denom : 0;
}

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
// Pitch is a little looser than yaw because tilting the head up/down displaces
// the nose less in the 2D image plane than turning left/right does — a small
// upward tilt was consistently landing in the 0.04-0.05 band and not firing.
export const YAW_THRESHOLD = 0.08;
export const PITCH_THRESHOLD = 0.04;

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
  /**
   * Inner grid (forehead, brows, eyes, nose, cheeks, mouth, chin) estimated
   * from YuNet's 5 landmarks and, when present, the face box. This is capture
   * feedback in the face's own axes, not a 468-point landmarker and not an
   * identity key. More lines do not make one face unique among billions of
   * people. Identity is the SFace embedding from the neutral portrait and the
   * pose captures.
   */
  grid: Point[][];
};

/**
 * YuNet supplies this many landmarks. The mesh is drawn from them.
 * Line count is not a uniqueness proof.
 */
export const MESH_SOURCE_LANDMARKS = 5;

export const FACE_MARK_REGIONS = ["forehead", "left cheek", "right cheek", "nose", "chin", "jaw"] as const;
export type FaceRegion = (typeof FACE_MARK_REGIONS)[number];

/**
 * Optional capture note for a darker spot (mole, birthmark, scar).
 * `point` exists only so the current overlay can draw a ring. Do not send it,
 * store it, or treat it as an identity. The camera image is not part of this
 * value. An empty list is a normal result.
 */
export type FaceMark = {
  region: FaceRegion;
  point: Point;
  /** Absolute gap versus nearby skin, divided by 255. Not a measurement of the spot. */
  contrast: number;
};

type FaceBasis = {
  u: Point;
  v: Point;
  at: (origin: Point, a: number, b: number) => Point;
  eyeDist: number;
  height: number;
  eyeMid: Point;
  mouthMid: Point;
  center: Point;
  halfWidth: number;
  top: number;
  bottom: number;
  rightEye: Point;
  leftEye: Point;
  nose: Point;
  rightMouth: Point;
  leftMouth: Point;
};

function meshArgs(
  samplesOrBox?: number | number[] | null,
  bbox?: number[] | null,
): { samples: number; bbox: number[] | null } {
  if (typeof samplesOrBox === "number" && Number.isFinite(samplesOrBox)) {
    const samples = Math.max(8, Math.min(128, Math.round(samplesOrBox)));
    return { samples, bbox: bbox ?? null };
  }
  if (Array.isArray(samplesOrBox)) return { samples: 32, bbox: samplesOrBox };
  return { samples: 32, bbox: bbox ?? null };
}

function faceBasis(landmarks: number[][] | undefined | null, bbox?: number[] | null): FaceBasis | null {
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
  const axis: Point = [(eyeMid[0] + mouthMid[0]) / 2, (eyeMid[1] + mouthMid[1]) / 2];
  const lean = ((nose[0] - axis[0]) * u[0] + (nose[1] - axis[1]) * u[1]) * 0.45;
  const center = at(eyeMid, lean, height * 0.42);
  let halfWidth = eyeDist * 1.02;
  let top = height * 1.75;
  let bottom = height * 1.32;
  if (bbox && bbox.length >= 4) {
    const [x, y, w, h] = bbox.map(Number);
    if ([x, y, w, h].every((n) => Number.isFinite(n)) && w > 1 && h > 1) {
      let maxA = 0;
      let minB = 0;
      let maxB = 0;
      const corners: Point[] = [[x, y], [x + w, y], [x, y + h], [x + w, y + h]];
      for (const corner of corners) {
        const dx = corner[0] - center[0];
        const dy = corner[1] - center[1];
        maxA = Math.max(maxA, Math.abs(dx * u[0] + dy * u[1]));
        const b = dx * v[0] + dy * v[1];
        minB = Math.min(minB, b);
        maxB = Math.max(maxB, b);
      }
      const clamp = (value: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, value));
      // The box is axis-aligned, so a tilt inflates it. Let it nudge the
      // outline by at most 25% and no further.
      top = clamp(-minB * 0.96, top * 0.85, top * 1.25);
      bottom = clamp(maxB * 0.96, bottom * 0.85, bottom * 1.25);
      halfWidth = clamp(maxA * 0.78, halfWidth * 0.85, halfWidth * 1.2);
    }
  }
  return {
    u, v, at, eyeDist, height, eyeMid, mouthMid, center, halfWidth, top, bottom,
    rightEye, leftEye, nose, rightMouth, leftMouth,
  };
}

function halfWidthAt(basis: FaceBasis, bFromCenter: number): number {
  const { top, bottom, halfWidth } = basis;
  if (bFromCenter <= -top || bFromCenter >= bottom) return 0;
  if (bFromCenter < 0) {
    const s = -bFromCenter / top;
    return halfWidth * Math.sqrt(Math.max(0, 1 - s * s));
  }
  const s = bFromCenter / bottom;
  const jaw = 1 - 0.22 * s * s;
  return halfWidth * jaw * Math.sqrt(Math.max(0, 1 - s * s));
}

function fromCenter(basis: FaceBasis, point: Point): [number, number] {
  const dx = point[0] - basis.center[0];
  const dy = point[1] - basis.center[1];
  return [dx * basis.u[0] + dy * basis.u[1], dx * basis.v[0] + dy * basis.v[1]];
}

/** Ease grid lines around the eyes and the nose so the estimate reads as a face, not a flat oval. */
function bend(basis: FaceBasis, a: number, b: number): [number, number] {
  let x = a;
  let y = b;
  for (const eye of [basis.rightEye, basis.leftEye]) {
    const [ex, ey] = fromCenter(basis, eye);
    const dx = a - ex;
    const dy = b - ey;
    const rx = basis.eyeDist * 0.28;
    const ry = basis.eyeDist * 0.16;
    const n = (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry);
    if (n > 0 && n < 1) {
      const push = (1 - n) * basis.eyeDist * 0.07;
      const len = Math.hypot(dx, dy) || 1;
      x += (dx / len) * push;
      y += (dy / len) * push;
    }
  }
  const [nx, ny] = fromCenter(basis, basis.nose);
  const dx = x - nx;
  const dy = y - ny;
  const nrx = basis.eyeDist * 0.2;
  const nry = basis.height * 0.22;
  const nn = (dx * dx) / (nrx * nrx) + (dy * dy) / (nry * nry);
  if (nn > 0 && nn < 1) {
    const flare = (1 - nn) * basis.eyeDist * (dy < 0 ? -0.035 : 0.05);
    const side = dx === 0 ? a : dx;
    x += Math.sign(side) * Math.abs(flare);
  }
  const cap = halfWidthAt(basis, y) * 0.96;
  if (cap <= 0.5) {
    return [0, Math.max(-basis.top * 0.92, Math.min(basis.bottom * 0.92, y))];
  }
  return [Math.max(-cap, Math.min(cap, x)), y];
}

function dedupeRows(values: number[], gap: number): number[] {
  const sorted = [...values].filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  const out: number[] = [];
  for (const value of sorted) {
    if (!out.length || value - out[out.length - 1] > gap) out.push(value);
  }
  return out;
}

/**
 * Pale wireframe for the learner-check camera. "full" draws an outer contour
 * plus an inner grid. "features" draws the face oval plus the eyes and the
 * nose — that is what the live scan shows, so it does not build the grid on
 * every camera tick. The lines follow the eye line, so a tilted head tilts
 * them too. Pass the face box (x, y, w, h) when YuNet has one; it only nudges
 * the outline. Returns null when the five landmarks cannot describe a face.
 */
export function faceContour(
  landmarks: number[][] | undefined | null,
  samplesOrBox?: number | number[] | null,
  bbox?: number[] | null,
  detail: "full" | "features" = "full",
): FaceContour | null {
  const args = meshArgs(samplesOrBox, bbox);
  const basis = faceBasis(landmarks, args.bbox);
  if (!basis) return null;
  const { at, eyeDist, height, eyeMid, mouthMid, center, halfWidth, top, bottom } = basis;
  const { rightEye, leftEye, nose, rightMouth, leftMouth } = basis;
  const outline: Point[] = [];
  for (let i = 0; i < args.samples; i += 1) {
    const t = (i / args.samples) * Math.PI * 2;
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
  const rightEyeLoop = eye(rightEye);
  const leftEyeLoop = eye(leftEye);
  if (detail === "features") {
    return { outline, rightEye: rightEyeLoop, leftEye: leftEyeLoop, nose: noseStroke, mouth: [], grid: [] };
  }
  const eyeB = fromCenter(basis, eyeMid)[1];
  const noseB = fromCenter(basis, nose)[1];
  const mouthB = fromCenter(basis, mouthMid)[1];
  const rows = dedupeRows([
    -top * 0.78,
    -top * 0.56,
    -top * 0.34,
    eyeB,
    eyeB + height * 0.22,
    noseB,
    (noseB + mouthB) / 2,
    mouthB - height * 0.06,
    mouthB + height * 0.12,
    bottom * 0.72,
  ], height * 0.08);
  const grid: Point[][] = [];
  for (const b of rows) {
    const half = halfWidthAt(basis, b);
    if (half < 2) continue;
    const line: Point[] = [];
    const steps = 10;
    for (let i = 0; i <= steps; i += 1) {
      const a = -half * 0.92 + (half * 1.84 * i) / steps;
      const [ba, bb] = bend(basis, a, b);
      line.push(at(center, ba, bb));
    }
    grid.push(line);
  }
  const stepsDown = 12;
  for (const fraction of [-0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75]) {
    const line: Point[] = [];
    for (let i = 0; i <= stepsDown; i += 1) {
      const b = -top * 0.9 + ((top * 0.9 + bottom * 0.86) * i) / stepsDown;
      const half = halfWidthAt(basis, b);
      if (half < 1) continue;
      const [ba, bb] = bend(basis, fraction * half * 0.92, b);
      line.push(at(center, ba, bb));
    }
    if (line.length >= 2) grid.push(line);
  }
  const brow = (eye: Point): Point[] => {
    const origin = at(eye, 0, -eyeDist * 0.14);
    const [ox, oy] = fromCenter(basis, origin);
    const line: Point[] = [];
    const n = 6;
    for (let i = 0; i <= n; i += 1) {
      const t = Math.PI + (Math.PI * i) / n;
      const [ba, bb] = bend(
        basis,
        ox + Math.cos(t) * eyeDist * 0.22,
        oy + Math.sin(t) * eyeDist * 0.07,
      );
      line.push(at(center, ba, bb));
    }
    return line;
  };
  grid.push(brow(rightEye), brow(leftEye));
  return { outline, rightEye: rightEyeLoop, leftEye: leftEyeLoop, nose: noseStroke, mouth, grid };
}

function ellipseHit(a: number, b: number, cx: number, cy: number, rx: number, ry: number): boolean {
  if (rx <= 0 || ry <= 0) return false;
  const dx = a - cx;
  const dy = b - cy;
  return (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1;
}

/** Eyes, brows, nostrils, and the mouth are dark on almost every face. Skip them. */
function excludedZone(basis: FaceBasis, a: number, b: number): boolean {
  const { eyeDist, height } = basis;
  for (const eye of [basis.rightEye, basis.leftEye]) {
    const [ex, ey] = fromCenter(basis, eye);
    if (ellipseHit(a, b, ex, ey, eyeDist * 0.3, eyeDist * 0.2)) return true;
  }
  const eyeB = fromCenter(basis, basis.eyeMid)[1];
  if (b < eyeB - height * 0.08 && b > eyeB - height * 0.36 && Math.abs(a) < eyeDist * 0.95) return true;
  const [nx, ny] = fromCenter(basis, basis.nose);
  if (ellipseHit(a, b, nx, ny + height * 0.06, eyeDist * 0.22, height * 0.12)) return true;
  const [mx, my] = fromCenter(basis, basis.mouthMid);
  const mouthW = Math.hypot(
    basis.leftMouth[0] - basis.rightMouth[0],
    basis.leftMouth[1] - basis.rightMouth[1],
  );
  if (ellipseHit(a, b, mx, my, Math.max(eyeDist * 0.34, mouthW * 0.7), height * 0.28)) return true;
  return false;
}

function insideFace(basis: FaceBasis, a: number, b: number, inset: number): boolean {
  const limit = halfWidthAt(basis, b);
  if (limit <= 1) return false;
  if (b <= -basis.top * inset || b >= basis.bottom * inset) return false;
  return Math.abs(a) <= limit * inset;
}

function regionFor(basis: FaceBasis, a: number, b: number): FaceRegion {
  const { eyeDist, height } = basis;
  const eyeB = fromCenter(basis, basis.eyeMid)[1];
  const mouthB = fromCenter(basis, basis.mouthMid)[1];
  if (b < eyeB - height * 0.4) return "forehead";
  if (b > mouthB + height * 0.28) return "chin";
  const nx = fromCenter(basis, basis.nose)[0];
  if (Math.abs(a - nx) < eyeDist * 0.2 && b < mouthB) return "nose";
  if (Math.abs(a) > eyeDist * 0.72 && b > mouthB - height * 0.1) return "jaw";
  // +u points at the person's left eye.
  return a >= 0 ? "left cheek" : "right cheek";
}

function lumaOf(rgba: ArrayLike<number>, width: number, x: number, y: number): number {
  const i = (y * width + x) * 4;
  return 0.2126 * rgba[i] + 0.7152 * rgba[i + 1] + 0.0722 * rgba[i + 2];
}

/**
 * Find up to three compact spots inside the face that are darker than the
 * surrounding skin, or lighter on a cheek. Eyes, brows, nostrils, and the
 * mouth are ignored. A broad shadow is ignored too.
 *
 * This is a luminance blob heuristic. It is not a medical or forensic read.
 * An empty list means "no marker" — draw the mesh alone. Nothing returned
 * here is a photo: only a region name, a point, and a contrast figure.
 */
export function faceMarks(
  rgba: ArrayLike<number>,
  width: number,
  heightPx: number,
  landmarks: number[][] | undefined | null,
  bbox?: number[] | null,
): FaceMark[] {
  if (!width || !heightPx || width < 2 || heightPx < 2) return [];
  if (rgba.length < width * heightPx * 4) return [];
  const basis = faceBasis(landmarks, bbox);
  if (!basis) return [];
  const stride = Math.max(1, Math.round(Math.min(width, heightPx) / 120));
  type Sample = { x: number; y: number; luma: number; a: number; b: number; skip: boolean };
  const samples: Sample[] = [];
  const skin: number[] = [];
  for (let y = 0; y < heightPx; y += stride) {
    for (let x = 0; x < width; x += stride) {
      const dx = x - basis.center[0];
      const dy = y - basis.center[1];
      const a = dx * basis.u[0] + dy * basis.u[1];
      const b = dx * basis.v[0] + dy * basis.v[1];
      if (!insideFace(basis, a, b, 0.9)) continue;
      const luma = lumaOf(rgba, width, x, y);
      const skip = excludedZone(basis, a, b);
      if (!skip && luma > 30 && luma < 245) skin.push(luma);
      samples.push({ x, y, luma, a, b, skip });
    }
  }
  if (skin.length < 12) return [];
  skin.sort((p, q) => p - q);
  const median = skin[Math.floor(skin.length / 2)];
  const darkCut = Math.min(median - 42, median * 0.75);
  const lightCut = Math.max(median + 58, median * 1.22);
  type Hit = Sample & { kind: "dark" | "light" };
  const hits: Hit[] = [];
  for (const sample of samples) {
    if (sample.skip || !insideFace(basis, sample.a, sample.b, 0.8)) continue;
    if (sample.luma <= darkCut) hits.push({ ...sample, kind: "dark" });
    else if (sample.luma >= lightCut) hits.push({ ...sample, kind: "light" });
  }
  if (!hits.length || hits.length / samples.length > 0.22) return [];
  const cell = Math.max(2, Math.round(basis.eyeDist * 0.09));
  const buckets = new Map<string, Hit[]>();
  for (const hit of hits) {
    const key = `${Math.floor(hit.x / cell)},${Math.floor(hit.y / cell)},${hit.kind}`;
    const list = buckets.get(key);
    if (list) list.push(hit);
    else buckets.set(key, [hit]);
  }
  const neighborKeys = (key: string): string[] => {
    const [xs, ys, kind] = key.split(",");
    const cx = Number(xs);
    const cy = Number(ys);
    return [
      `${cx - 1},${cy},${kind}`,
      `${cx + 1},${cy},${kind}`,
      `${cx},${cy - 1},${kind}`,
      `${cx},${cy + 1},${kind}`,
    ];
  };
  const seen = new Set<string>();
  const marks: FaceMark[] = [];
  for (const start of buckets.keys()) {
    if (seen.has(start)) continue;
    const stack = [start];
    const group: Hit[] = [];
    seen.add(start);
    while (stack.length) {
      const key = stack.pop() as string;
      group.push(...(buckets.get(key) ?? []));
      for (const next of neighborKeys(key)) {
        if (seen.has(next) || !buckets.has(next)) continue;
        seen.add(next);
        stack.push(next);
      }
    }
    if (group.length < 3 || group.length / samples.length > 0.06) continue;
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    let lumaSum = 0;
    let aSum = 0;
    let bSum = 0;
    let xSum = 0;
    let ySum = 0;
    for (const hit of group) {
      minX = Math.min(minX, hit.x);
      maxX = Math.max(maxX, hit.x);
      minY = Math.min(minY, hit.y);
      maxY = Math.max(maxY, hit.y);
      lumaSum += hit.luma;
      aSum += hit.a;
      bSum += hit.b;
      xSum += hit.x;
      ySum += hit.y;
    }
    const bw = maxX - minX + cell;
    const bh = maxY - minY + cell;
    const aspect = Math.max(bw, bh) / Math.max(1, Math.min(bw, bh));
    if (aspect > 4.5) continue;
    const kind = group[0]?.kind;
    if (!kind) continue;
    const region = regionFor(basis, aSum / group.length, bSum / group.length);
    if (kind === "light" && region !== "left cheek" && region !== "right cheek") continue;
    marks.push({
      region,
      point: [xSum / group.length, ySum / group.length],
      contrast: Math.abs(median - lumaSum / group.length) / 255,
    });
  }
  marks.sort((p, q) => q.contrast - p.contrast);
  const unique: FaceMark[] = [];
  const used = new Set<string>();
  for (const mark of marks) {
    if (used.has(mark.region)) continue;
    used.add(mark.region);
    unique.push(mark);
    if (unique.length === 3) break;
  }
  return unique;
}

/**
 * A region is kept when it shows up in `minHits` of the recent frames.
 * Live video uses this so a one-frame shadow does not flash a marker.
 * A single still should call `faceMarks` directly — one photo cannot repeat.
 */
export function stableFaceMarks(history: readonly FaceMark[][], minHits = 3): FaceMark[] {
  const recent = history.slice(-5);
  const buckets = new Map<string, { hits: number; x: number; y: number; contrast: number }>();
  for (const frame of recent) {
    const seen = new Set<string>();
    for (const mark of frame) {
      if (seen.has(mark.region)) continue;
      seen.add(mark.region);
      const slot = buckets.get(mark.region) ?? { hits: 0, x: 0, y: 0, contrast: 0 };
      slot.hits += 1;
      slot.x += mark.point[0];
      slot.y += mark.point[1];
      slot.contrast = Math.max(slot.contrast, mark.contrast);
      buckets.set(mark.region, slot);
    }
  }
  const out: FaceMark[] = [];
  for (const [region, slot] of buckets) {
    if (slot.hits < minHits) continue;
    out.push({
      region: region as FaceRegion,
      point: [slot.x / slot.hits, slot.y / slot.hits],
      contrast: slot.contrast,
    });
  }
  out.sort((p, q) => q.contrast - p.contrast);
  return out.slice(0, 3);
}

const B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/** Decode a base64 JPEG/PNG payload. Strips a data-URL prefix. Returns null on garbage. */
export function bytesFromBase64(input: string): Uint8Array | null {
  const cleaned = input.replace(/^data:image\/[a-zA-Z0-9.+-]+;base64,/, "").replace(/[^A-Za-z0-9+/=]/g, "");
  if (!cleaned || cleaned.length % 4 === 1) return null;
  const out: number[] = [];
  for (let i = 0; i < cleaned.length; i += 4) {
    const c0 = cleaned[i] ?? "";
    const c1 = cleaned[i + 1] ?? "";
    const c2 = cleaned[i + 2] ?? "";
    const c3 = cleaned[i + 3] ?? "";
    const a = B64_ALPHABET.indexOf(c0);
    const b = B64_ALPHABET.indexOf(c1);
    const c = c2 === "=" ? -1 : B64_ALPHABET.indexOf(c2);
    const d = c3 === "=" ? -1 : B64_ALPHABET.indexOf(c3);
    if (a < 0 || b < 0 || (c2 !== "=" && c < 0) || (c3 !== "=" && d < 0)) return null;
    out.push((a << 2) | (b >> 4));
    if (c >= 0) out.push(((b & 15) << 4) | (c >> 2));
    if (c >= 0 && d >= 0) out.push(((c & 3) << 6) | d);
  }
  return Uint8Array.from(out);
}

export type JpegLuma = {
  width: number;
  height: number;
  sourceWidth: number;
  sourceHeight: number;
  /** Grayscale RGBA (R=G=B=JPEG Y). Small enough to scan for marks. */
  rgba: Uint8Array;
};

const JPEG_ZIGZAG = [
  0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
  12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
  35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
  58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
];

type HuffTable = { maxCode: number[]; minCode: number[]; valPtr: number[]; symbols: number[] };
type FrameComp = { id: number; h: number; v: number; tq: number };
type ScanComp = FrameComp & { dcId: number; acId: number };

function buildHuffman(counts: number[], symbols: number[]): HuffTable {
  const maxCode = new Array<number>(17).fill(-1);
  const minCode = new Array<number>(17).fill(0);
  const valPtr = new Array<number>(17).fill(0);
  let code = 0;
  let si = 0;
  for (let len = 1; len <= 16; len += 1) {
    const count = counts[len] ?? 0;
    if (count) {
      valPtr[len] = si;
      minCode[len] = code;
      si += count;
      code += count;
      maxCode[len] = code - 1;
    }
    code <<= 1;
  }
  return { maxCode, minCode, valPtr, symbols };
}

/**
 * Baseline JPEG → a downscaled luma image. Progressive and other SOF markers
 * return null; the mesh still draws, just without markers. Only Y is kept.
 * The full-resolution plane is not returned.
 */
export function decodeJpegLuma(data: Uint8Array, maxEdge = 240): JpegLuma | null {
  if (!data || data.length < 4 || data[0] !== 0xff || data[1] !== 0xd8) return null;
  const edge = Number.isFinite(maxEdge) && maxEdge >= 32 ? Math.min(480, Math.round(maxEdge)) : 240;
  const quant: (Uint16Array | null)[] = [null, null, null, null];
  const dcTables: (HuffTable | null)[] = [null, null, null, null];
  const acTables: (HuffTable | null)[] = [null, null, null, null];
  let frame: { width: number; height: number; comps: FrameComp[] } | null = null;
  let restart = 0;
  let p = 2;
  const u16 = (): number | null => {
    if (p + 1 >= data.length) return null;
    const value = (data[p] << 8) | data[p + 1];
    p += 2;
    return value;
  };
  while (p + 1 < data.length) {
    if (data[p] !== 0xff) return null;
    while (p < data.length && data[p] === 0xff) p += 1;
    if (p >= data.length) return null;
    const marker = data[p];
    p += 1;
    if (marker === 0xd9) return null;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    const length = u16();
    if (length == null || length < 2 || p + length - 2 > data.length) return null;
    const end = p + length - 2;
    if (marker === 0xdd) {
      restart = (data[p] << 8) | data[p + 1];
      p = end;
      continue;
    }
    if (marker === 0xc0) {
      const precision = data[p];
      const height = (data[p + 1] << 8) | data[p + 2];
      const width = (data[p + 3] << 8) | data[p + 4];
      const n = data[p + 5];
      if (precision !== 8 || !width || !height || n < 1 || n > 4) return null;
      // A multi-megapixel still would stall the UI in this pure-JS decoder.
      // Skip markers; the mesh is drawn from the landmarks either way.
      if (width * height > 5_000_000) return null;
      const comps: FrameComp[] = [];
      let q = p + 6;
      for (let i = 0; i < n; i += 1) {
        if (q + 2 >= end) return null;
        const id = data[q];
        const hv = data[q + 1];
        const h = hv >> 4;
        const v = hv & 15;
        const tq = data[q + 2];
        if (h < 1 || h > 4 || v < 1 || v > 4 || tq > 3) return null;
        comps.push({ id, h, v, tq });
        q += 3;
      }
      frame = { width, height, comps };
      p = end;
      continue;
    }
    // Other start-of-frame markers (progressive, lossless). DHT is 0xC4 and must stay.
    if (
      marker === 0xc1 || marker === 0xc2 || marker === 0xc3
      || (marker >= 0xc5 && marker <= 0xc7)
      || (marker >= 0xc9 && marker <= 0xcb)
      || (marker >= 0xcd && marker <= 0xcf)
    ) return null;
    if (marker === 0xdb) {
      let q = p;
      while (q < end) {
        const info = data[q];
        q += 1;
        const prec = info >> 4;
        const id = info & 15;
        if (prec !== 0 || id > 3 || q + 64 > end) return null;
        const table = new Uint16Array(64);
        for (let i = 0; i < 64; i += 1) table[i] = data[q + i];
        quant[id] = table;
        q += 64;
      }
      p = end;
      continue;
    }
    if (marker === 0xc4) {
      let q = p;
      while (q < end) {
        const info = data[q];
        q += 1;
        const cls = info >> 4;
        const id = info & 15;
        if ((cls !== 0 && cls !== 1) || id > 3 || q + 16 > end) return null;
        const counts = [0];
        let nsym = 0;
        for (let i = 0; i < 16; i += 1) {
          const count = data[q + i];
          counts.push(count);
          nsym += count;
        }
        q += 16;
        if (q + nsym > end) return null;
        const symbols: number[] = [];
        for (let i = 0; i < nsym; i += 1) symbols.push(data[q + i]);
        q += nsym;
        const table = buildHuffman(counts, symbols);
        if (cls === 0) dcTables[id] = table;
        else acTables[id] = table;
      }
      p = end;
      continue;
    }
    if (marker === 0xda) {
      if (!frame) return null;
      const decoded = decodeJpegScan(data, p, end, frame, quant, dcTables, acTables, restart, edge);
      return decoded;
    }
    p = end;
  }
  return null;
}

function decodeJpegScan(
  data: Uint8Array,
  header: number,
  headerEnd: number,
  frame: { width: number; height: number; comps: FrameComp[] },
  quant: (Uint16Array | null)[],
  dcTables: (HuffTable | null)[],
  acTables: (HuffTable | null)[],
  restart: number,
  maxEdge: number,
): JpegLuma | null {
  const n = data[header];
  if (!n || header + 1 + n * 2 + 3 > headerEnd) return null;
  const scan: ScanComp[] = [];
  let q = header + 1;
  for (let i = 0; i < n; i += 1) {
    const id = data[q];
    const tables = data[q + 1];
    q += 2;
    const comp = frame.comps.find((item) => item.id === id);
    if (!comp) return null;
    scan.push({ ...comp, dcId: tables >> 4, acId: tables & 15 });
  }
  const spectralStart = data[q];
  const spectralEnd = data[q + 1];
  if (spectralStart !== 0 || spectralEnd !== 63) return null;
  let hMax = 1;
  let vMax = 1;
  for (const comp of frame.comps) {
    hMax = Math.max(hMax, comp.h);
    vMax = Math.max(vMax, comp.v);
  }
  const luma = scan.reduce((best, comp) => (comp.h * comp.v > best.h * best.v ? comp : best), scan[0]);
  if (!luma || luma.h !== hMax || luma.v !== vMax) return null;
  const lumaQuant = quant[luma.tq];
  if (!lumaQuant) return null;
  for (const comp of scan) {
    if (!quant[comp.tq] || !dcTables[comp.dcId] || !acTables[comp.acId]) return null;
  }
  const reader = { pos: headerEnd, bitBuf: 0, bitCount: 0, bad: false };
  const nextByte = (): number | null => {
    if (reader.pos >= data.length) {
      reader.bad = true;
      return null;
    }
    const b = data[reader.pos];
    reader.pos += 1;
    if (b !== 0xff) return b;
    if (reader.pos >= data.length) {
      reader.bad = true;
      return null;
    }
    let marker = data[reader.pos];
    reader.pos += 1;
    while (marker === 0xff && reader.pos < data.length) {
      marker = data[reader.pos];
      reader.pos += 1;
    }
    if (marker === 0x00) return 0xff;
    reader.bad = true;
    return null;
  };
  const readBit = (): number => {
    if (reader.bitCount === 0) {
      const b = nextByte();
      if (b == null) return 0;
      reader.bitBuf = b;
      reader.bitCount = 8;
    }
    reader.bitCount -= 1;
    return (reader.bitBuf >> reader.bitCount) & 1;
  };
  const receive = (len: number): number => {
    if (len <= 0) return 0;
    let value = 0;
    for (let i = 0; i < len; i += 1) value = (value << 1) | readBit();
    if (value < (1 << (len - 1))) value += (-1 << len) + 1;
    return value;
  };
  const decodeSymbol = (table: HuffTable): number | null => {
    let code = 0;
    for (let len = 1; len <= 16; len += 1) {
      code = (code << 1) | readBit();
      const maxCode = table.maxCode[len] ?? -1;
      const minCode = table.minCode[len] ?? 0;
      if (maxCode >= 0 && code >= minCode && code <= maxCode) {
        const index = (table.valPtr[len] ?? 0) + (code - minCode);
        const symbol = table.symbols[index];
        return symbol === undefined ? null : symbol;
      }
    }
    return null;
  };
  const decodeBlock = (comp: ScanComp, pred: number): { pred: number; block: Float64Array } | null => {
    const dc = dcTables[comp.dcId];
    const ac = acTables[comp.acId];
    const table = quant[comp.tq];
    if (!dc || !ac || !table) return null;
    const category = decodeSymbol(dc);
    if (category == null || category > 11) return null;
    const diff = receive(category);
    const nextPred = pred + diff;
    const block = new Float64Array(64);
    block[0] = nextPred * table[0];
    let k = 0;
    while (k < 63) {
      const symbol = decodeSymbol(ac);
      if (symbol == null) return null;
      if (symbol === 0) break;
      const run = symbol >> 4;
      const size = symbol & 15;
      if (size === 0) {
        if (run !== 15) return null;
        k += 16;
        continue;
      }
      k += run + 1;
      if (k > 63) return null;
      const coeff = receive(size);
      block[JPEG_ZIGZAG[k]] = coeff * table[k];
      if (reader.bad) return null;
    }
    return { pred: nextPred, block };
  };
  const idct = (block: Float64Array): void => {
    const tmp = new Float64Array(64);
    for (let v = 0; v < 8; v += 1) {
      for (let x = 0; x < 8; x += 1) {
        let sum = 0;
        for (let u = 0; u < 8; u += 1) {
          const cu = u === 0 ? 0.7071067811865476 : 1;
          sum += cu * block[v * 8 + u] * Math.cos(((2 * x + 1) * u * Math.PI) / 16);
        }
        tmp[v * 8 + x] = sum;
      }
    }
    for (let x = 0; x < 8; x += 1) {
      for (let y = 0; y < 8; y += 1) {
        let sum = 0;
        for (let v = 0; v < 8; v += 1) {
          const cv = v === 0 ? 0.7071067811865476 : 1;
          sum += cv * tmp[v * 8 + x] * Math.cos(((2 * y + 1) * v * Math.PI) / 16);
        }
        block[y * 8 + x] = sum / 4;
      }
    }
  };
  const mcuCols = Math.ceil(frame.width / (hMax * 8));
  const mcuRows = Math.ceil(frame.height / (vMax * 8));
  const plane = new Uint8Array(frame.width * frame.height);
  const preds = scan.map(() => 0);
  let mcuIndex = 0;
  const readRestart = (): boolean => {
    reader.bitCount = 0;
    reader.bitBuf = 0;
    if (reader.pos >= data.length || data[reader.pos] !== 0xff) return false;
    reader.pos += 1;
    while (reader.pos < data.length && data[reader.pos] === 0xff) reader.pos += 1;
    if (reader.pos >= data.length) return false;
    const marker = data[reader.pos];
    reader.pos += 1;
    return marker >= 0xd0 && marker <= 0xd7;
  };
  for (let my = 0; my < mcuRows; my += 1) {
    for (let mx = 0; mx < mcuCols; mx += 1) {
      if (restart > 0 && mcuIndex > 0 && mcuIndex % restart === 0) {
        if (!readRestart()) return null;
        preds.fill(0);
        reader.bad = false;
      }
      for (let ci = 0; ci < scan.length; ci += 1) {
        const comp = scan[ci];
        for (let by = 0; by < comp.v; by += 1) {
          for (let bx = 0; bx < comp.h; bx += 1) {
            const decoded = decodeBlock(comp, preds[ci] ?? 0);
            if (!decoded || reader.bad) return null;
            preds[ci] = decoded.pred;
            if (comp.id !== luma.id) continue;
            idct(decoded.block);
            const x0 = (mx * comp.h + bx) * 8;
            const y0 = (my * comp.v + by) * 8;
            for (let j = 0; j < 8; j += 1) {
              const y = y0 + j;
              if (y >= frame.height) continue;
              for (let i = 0; i < 8; i += 1) {
                const x = x0 + i;
                if (x >= frame.width) continue;
                const value = decoded.block[j * 8 + i] + 128;
                plane[y * frame.width + x] = value < 0 ? 0 : value > 255 ? 255 : value;
              }
            }
          }
        }
      }
      mcuIndex += 1;
    }
  }
  const scale = Math.min(1, maxEdge / Math.max(frame.width, frame.height));
  const width = Math.max(1, Math.round(frame.width * scale));
  const height = Math.max(1, Math.round(frame.height * scale));
  const rgba = new Uint8Array(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    const y0 = Math.min(frame.height - 1, Math.floor(y / scale));
    const y1 = Math.min(frame.height, Math.max(y0 + 1, Math.floor((y + 1) / scale)));
    for (let x = 0; x < width; x += 1) {
      const x0 = Math.min(frame.width - 1, Math.floor(x / scale));
      const x1 = Math.min(frame.width, Math.max(x0 + 1, Math.floor((x + 1) / scale)));
      let sum = 0;
      let count = 0;
      for (let yy = y0; yy < y1; yy += 1) {
        const row = yy * frame.width;
        for (let xx = x0; xx < x1; xx += 1) {
          sum += plane[row + xx];
          count += 1;
        }
      }
      const value = count ? Math.round(sum / count) : 0;
      const i = (y * width + x) * 4;
      rgba[i] = value;
      rgba[i + 1] = value;
      rgba[i + 2] = value;
      rgba[i + 3] = 255;
    }
  }
  return { width, height, sourceWidth: frame.width, sourceHeight: frame.height, rgba };
}

/**
 * Marks for one JPEG still. Landmarks must be in that JPEG's pixel space
 * (`frameSize` is the detector frame). A size mismatch, or a JPEG this
 * decoder cannot read, yields no markers. The bytes are not retained.
 */
export function faceMarksFromJpeg(
  encoded: string | Uint8Array,
  landmarks: number[][] | undefined | null,
  frameSize: [number, number] | number[],
  bbox?: number[] | null,
  maxEdge = 240,
): FaceMark[] {
  const bytes = typeof encoded === "string" ? bytesFromBase64(encoded) : encoded;
  if (!bytes || frameSize.length < 2) return [];
  const frameW = Number(frameSize[0]);
  const frameH = Number(frameSize[1]);
  if (!frameW || !frameH) return [];
  const image = decodeJpegLuma(bytes, maxEdge);
  if (!image) return [];
  if (Math.abs(image.sourceWidth - frameW) > 4 || Math.abs(image.sourceHeight - frameH) > 4) return [];
  const sx = image.width / image.sourceWidth;
  const sy = image.height / image.sourceHeight;
  const scaled = (landmarks ?? []).map(([x, y]) => [x * sx, y * sy]);
  const scaledBox = bbox && bbox.length >= 4
    ? [bbox[0] * sx, bbox[1] * sy, bbox[2] * sx, bbox[3] * sy]
    : null;
  return faceMarks(image.rgba, image.width, image.height, scaled, scaledBox).map((mark) => ({
    ...mark,
    point: [mark.point[0] / sx, mark.point[1] / sy] as Point,
  }));
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

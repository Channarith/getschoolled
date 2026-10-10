// Pure gesture geometry, with no DOM or camera dependency, so it can be run and
// asserted directly by the test suite instead of only pattern-matched.
//
// MediaPipe landmarks are normalized to the frame, so a raw distance means
// different things depending on how far the child sits from the camera: a hand
// two metres back spans ~0.08 of the frame, one at arm's length ~0.25. Every
// threshold here is therefore in PALMS — multiples of the child's own
// wrist-to-middle-knuckle span — so a fist stays a fist at any distance.

export const FIST_MAX_PALMS = 1.6;     // closed ~1.1, extended ~2.4
export const HEART_TIPS_PALMS = 1.4;   // index fingertips meeting in the cleft
export const HEART_THUMBS_PALMS = 1.6; // thumb tips meeting at the bottom point
export const HEART_WRISTS_PALMS = 1.3; // wrists apart, else it is one clump
export const HEART_CLEFT_PALMS = 0.25; // tips sit below the knuckle peaks
export const HEART_POINT_PALMS = 0.45; // thumbs sit below that cleft
export const HEART_LOBES_PALMS = 1.1;  // knuckles spread into two lobes
export const KISS_NEAR_FACES = 0.85;   // hand-to-mouth, in face widths
export const KISS_AWAY_FACES = 1.5;    // travel needed to count as sent

// MediaPipe hand topology. Used when the runtime does not publish HAND_CONNECTIONS.
export const HAND_BONES = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
];

// object-fit: cover. Landmarks are fractions of the camera frame, and the
// stage crops that frame, so mapping them onto the full stage draws the
// skeleton off the hand. No video yet (pointer demo) uses the whole stage.
export function coverFrame(stageW, stageH, videoW, videoH) {
  const w = Number(stageW) || 0;
  const h = Number(stageH) || 0;
  const vw = Number(videoW) || 0;
  const vh = Number(videoH) || 0;
  if (!w || !h || !vw || !vh) return { x: 0, y: 0, w: w || 1, h: h || 1 };
  const scale = Math.max(w / vw, h / vh);
  const dw = vw * scale;
  const dh = vh * scale;
  return { x: (w - dw) / 2, y: (h - dh) / 2, w: dw, h: dh };
}

// The camera element is mirrored. Flip x inside the covered frame.
export function mapMirroredLandmark(point, frame) {
  const x = Number(point?.x) || 0;
  const y = Number(point?.y) || 0;
  return {
    x: frame.x + (1 - x) * frame.w,
    y: frame.y + y * frame.h,
    z: Number(point?.z) || 0,
  };
}

export function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

// Wrist to middle-finger knuckle: the one span that does not change when the
// fingers curl, so it is a stable ruler for every other measurement.
export function palmSpan(points) {
  const wrist = points?.[0];
  const knuckle = points?.[9];
  return wrist && knuckle ? Math.max(1e-4, distance(wrist, knuckle)) : 1;
}

// Comparing y alone only worked for an upright hand; a tilted or sideways hand
// read as "curled". Farther from the wrist than the middle joint is rotation-proof.
export function fingerExtended(points, tip, pip) {
  const wrist = points?.[0];
  if (!wrist || !points?.[tip] || !points?.[pip]) return false;
  return (
    distance(points[tip], wrist) >
    distance(points[pip], wrist) + 0.22 * palmSpan(points)
  );
}

export function handShape(points) {
  if (!points?.length) return null;
  const scale = palmSpan(points);
  const fingers = [
    fingerExtended(points, 8, 6),
    fingerExtended(points, 12, 10),
    fingerExtended(points, 16, 14),
    fingerExtended(points, 20, 18),
  ];
  const thumbOut = fingerExtended(points, 4, 2);
  const count = fingers.filter(Boolean).length + (thumbOut ? 1 : 0);
  const tipPalms =
    points[8] && points[0] ? distance(points[8], points[0]) / scale : 99;
  return {
    scale,
    count,
    thumbOut,
    tipPalms,
    indexUp: fingers[0] && !fingers[1] && !fingers[2] && !fingers[3],
    fist: count === 0 && tipPalms < FIST_MAX_PALMS,
  };
}

// Coloring only while fingers are out. A closed fist lifts the marker.
export function fingersPointed(shape) {
  return Boolean(shape) && !shape.fist && Number(shape.count) > 0;
}

export function heartRatios(a, b, scale) {
  if (!a?.[8] || !b?.[8] || !a[4] || !b[4] || !a[0] || !b[0] || !a[5] || !b[5]) return null;
  const tipY = (a[8].y + b[8].y) / 2;
  const knuckleY = (a[5].y + b[5].y) / 2;
  const thumbY = (a[4].y + b[4].y) / 2;
  return {
    tips: distance(a[8], b[8]) / scale,
    thumbs: distance(a[4], b[4]) / scale,
    wrists: distance(a[0], b[0]) / scale,
    // A heart dips between two lobes. A circle peaks at the fingertips, so this
    // is negative and the pose is rejected.
    cleft: (tipY - knuckleY) / scale,
    point: (thumbY - tipY) / scale,
    lobes: distance(a[5], b[5]) / scale,
  };
}

export function isHeartShape(ratios) {
  return (
    Boolean(ratios) &&
    ratios.tips < HEART_TIPS_PALMS &&
    ratios.thumbs < HEART_THUMBS_PALMS &&
    ratios.wrists > HEART_WRISTS_PALMS &&
    ratios.cleft > HEART_CLEFT_PALMS &&
    ratios.point > HEART_POINT_PALMS &&
    ratios.lobes > HEART_LOBES_PALMS &&
    ratios.lobes > ratios.tips + 0.4
  );
}

// Pointer-demo stand-in for MediaPipe: 21 landmarks in normalised frame space
// so the same handShape / heart / fist code runs without a camera.
export function syntheticHand(tip, { pose = "open", scale = 0.1 } = {}) {
  const nx = Math.max(0.08, Math.min(0.92, tip.x));
  const ny = Math.max(0.08, Math.min(0.75, tip.y));
  const wrist = { x: nx, y: ny + scale, z: 0 };
  const knuckle = { x: nx, y: ny + scale * 0.45, z: 0 };
  const pts = Array.from({ length: 21 }, () => ({ x: nx, y: ny, z: 0 }));
  pts[0] = wrist;
  pts[9] = knuckle;
  pts[2] = { x: nx - scale * 0.15, y: knuckle.y, z: 0 };
  const curledY = knuckle.y + scale * 0.08;
  const openY = ny - scale * 0.05;
  const fingerTips = [
    [8, 6, 0],
    [12, 10, 0.18],
    [16, 14, 0.32],
    [20, 18, 0.46],
  ];
  for (const [tipIdx, pipIdx, dx] of fingerTips) {
    const extend = pose === "open" || (pose === "index" && tipIdx === 8);
    pts[tipIdx] = { x: nx + dx * scale, y: extend ? openY : curledY, z: 0 };
    pts[pipIdx] = { x: nx + dx * scale * 0.5, y: knuckle.y, z: 0 };
  }
  pts[4] = {
    x: nx - scale * (pose === "fist" ? 0.08 : 0.45),
    y: pose === "fist" ? curledY : openY + scale * 0.12,
    z: 0,
  };
  return pts;
}

// A letter trace is a stroke, not a filled shape. A short line down the guide
// is enough. A tap or a scribble that never crosses the letter is not.
export function traceProgress(points, ageBand) {
  const samples = Array.isArray(points) ? points : [];
  const inside = samples.filter((point) => (
    point.x >= 0.22 && point.x <= 0.78 && point.y >= 0.18 && point.y <= 0.82
  ));
  let length = 0;
  for (let i = 1; i < inside.length; i += 1) {
    length += Math.hypot(inside[i].x - inside[i - 1].x, inside[i].y - inside[i - 1].y);
  }
  let minX = 1;
  let maxX = 0;
  let minY = 1;
  let maxY = 0;
  for (const point of inside) {
    minX = Math.min(minX, point.x);
    maxX = Math.max(maxX, point.x);
    minY = Math.min(minY, point.y);
    maxY = Math.max(maxY, point.y);
  }
  const span = inside.length ? Math.hypot(maxX - minX, maxY - minY) : 0;
  const young = ageBand === "4-6";
  const needLength = young ? 0.32 : 0.42;
  const needSpan = young ? 0.18 : 0.24;
  const needPoints = young ? 6 : 8;
  const insideRatio = samples.length ? inside.length / samples.length : 0;
  const percent = Math.round(100 * Math.min(
    1,
    length / needLength,
    span / needSpan,
    inside.length / needPoints,
    insideRatio / 0.25,
  ));
  return {
    percent: Number.isFinite(percent) ? percent : 0,
    passed: length >= needLength && span >= needSpan && inside.length >= needPoints && insideRatio >= 0.25,
    cells: inside.length,
  };
}

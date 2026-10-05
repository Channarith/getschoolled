// Pure gesture geometry, with no DOM or camera dependency, so it can be run and
// asserted directly by the test suite instead of only pattern-matched.
//
// MediaPipe landmarks are normalized to the frame, so a raw distance means
// different things depending on how far the child sits from the camera: a hand
// two metres back spans ~0.08 of the frame, one at arm's length ~0.25. Every
// threshold here is therefore in PALMS — multiples of the child's own
// wrist-to-middle-knuckle span — so a fist stays a fist at any distance.

export const FIST_MAX_PALMS = 1.6;     // closed ~1.1, extended ~2.4
export const HEART_TIPS_PALMS = 1.4;   // index fingertips meeting
export const HEART_THUMBS_PALMS = 1.6; // thumb tips meeting underneath
export const HEART_WRISTS_PALMS = 1.3; // wrists apart, else it is one clump
export const KISS_NEAR_FACES = 0.85;   // hand-to-mouth, in face widths
export const KISS_AWAY_FACES = 1.5;    // travel needed to count as sent

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

export function heartRatios(a, b, scale) {
  if (!a?.[8] || !b?.[8] || !a[4] || !b[4] || !a[0] || !b[0]) return null;
  return {
    tips: distance(a[8], b[8]) / scale,
    thumbs: distance(a[4], b[4]) / scale,
    wrists: distance(a[0], b[0]) / scale,
  };
}

export function isHeartShape(ratios) {
  return (
    Boolean(ratios) &&
    ratios.tips < HEART_TIPS_PALMS &&
    ratios.thumbs < HEART_THUMBS_PALMS &&
    ratios.wrists > HEART_WRISTS_PALMS
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

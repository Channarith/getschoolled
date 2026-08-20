/**
 * Distance-from-camera estimate from face bounding box.
 * Mirrors theodore_webcam_lab distance.py (face-size ratio heuristic).
 */

export type DistanceEstimate = {
  distanceM: number | null;
  faceSizeRatio: number | null;
  /** too_close | too_far | good | unknown */
  band: "too_close" | "too_far" | "good" | "unknown";
};

const REF_METRES = 0.65;
const REF_FACE_RATIO = 0.28;
const MIN_METRES = 0.35;
const MAX_METRES = 2.5;
const IDEAL_MIN = 0.45;
const IDEAL_MAX = 1.2;

export function faceSizeRatioFromBox(
  box: { width: number; height: number },
  frameW: number,
  frameH: number,
): number | null {
  if (frameW <= 0 || frameH <= 0 || box.width <= 0 || box.height <= 0) return null;
  return Math.max(0.02, Math.min(0.95, Math.max(box.width / frameW, box.height / frameH)));
}

export function metresFromFaceSizeRatio(ratio: number | null): number | null {
  if (ratio == null || ratio <= 0) return null;
  const effective = Math.max(0.08, ratio);
  const m = REF_METRES * (REF_FACE_RATIO / effective);
  return Math.round(Math.max(MIN_METRES, Math.min(MAX_METRES, m)) * 100) / 100;
}

export function estimateDistanceFromFaceBox(
  box: { width: number; height: number } | null,
  frameW: number,
  frameH: number,
): DistanceEstimate {
  if (!box) return { distanceM: null, faceSizeRatio: null, band: "unknown" };
  const ratio = faceSizeRatioFromBox(box, frameW, frameH);
  const distanceM = metresFromFaceSizeRatio(ratio);
  if (distanceM == null) return { distanceM: null, faceSizeRatio: ratio, band: "unknown" };
  let band: DistanceEstimate["band"] = "good";
  if (distanceM < IDEAL_MIN) band = "too_close";
  else if (distanceM > IDEAL_MAX) band = "too_far";
  return { distanceM, faceSizeRatio: ratio, band };
}

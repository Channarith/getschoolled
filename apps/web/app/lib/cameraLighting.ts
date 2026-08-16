/**
 * Pre-class camera / lighting readiness.
 *
 * Thresholds mirror theodore_webcam_lab VisionTuning defaults so a room that
 * would trip lighting_* / image_blurry gates cannot start a lesson.
 */

export type LightingVerdict =
  | "ready"
  | "fixable"
  | "blocked_dark"
  | "blocked_bright"
  | "blocked_blurry"
  | "blocked_no_face";

export type LightingThresholds = {
  lightUnderexposedLuma: number;
  lightOverexposedLuma: number;
  lightMaxClippedBlackRatio: number;
  lightMaxClippedWhiteRatio: number;
  lightMinQuality: number;
  sobelBinaryThreshold: number;
  sobelMinEdgeDensity: number;
  sharpnessReferenceGradient: number;
  sharpnessMinQuality: number;
  sharpnessGradientPercentile: number;
  /** Sustained face window (ms) before counting as present. */
  faceHoldMs: number;
};

/** Match VisionTuning() defaults in theodore_webcam_lab. */
export const DEFAULT_LIGHTING_THRESHOLDS: LightingThresholds = {
  lightUnderexposedLuma: 0.22,
  lightOverexposedLuma: 0.82,
  lightMaxClippedBlackRatio: 0.18,
  lightMaxClippedWhiteRatio: 0.12,
  lightMinQuality: 0.35,
  sobelBinaryThreshold: 0.18,
  sobelMinEdgeDensity: 0.035,
  sharpnessReferenceGradient: 0.35,
  sharpnessMinQuality: 0.30,
  sharpnessGradientPercentile: 95,
  faceHoldMs: 1200,
};

/** Relaxed gates when the learner explicitly enables Night vision. */
export const NIGHT_VISION_THRESHOLDS: LightingThresholds = {
  ...DEFAULT_LIGHTING_THRESHOLDS,
  lightUnderexposedLuma: 0.08,
  lightMaxClippedBlackRatio: 0.45,
  lightMinQuality: 0.12,
  sobelMinEdgeDensity: 0.008,
  sharpnessMinQuality: 0.12,
};

export type LightingMetrics = {
  meanLuminance: number;
  underexposedRatio: number;
  overexposedRatio: number;
  edgeDensity: number;
  sharpnessScore: number;
  lightQualityScore: number;
  underexposed: boolean;
  overexposed: boolean;
  blurry: boolean;
  lowEdgeDetail: boolean;
  flags: string[];
};

export type LightingReadiness = {
  verdict: LightingVerdict;
  metrics: LightingMetrics;
  facePresent: boolean;
  nightVision: boolean;
  message: string;
  tips: string[];
};

const SOBEL_MAX = 4 * Math.SQRT2;
const SOBEL_X = [
  [-1, 0, 1],
  [-2, 0, 2],
  [-1, 0, 1],
];
const SOBEL_Y = [
  [-1, -2, -1],
  [0, 0, 0],
  [1, 2, 1],
];

function clamp01(v: number): number {
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v;
}

export function analyzeLuminanceGrid(
  grid: number[][],
  thresholds: LightingThresholds = DEFAULT_LIGHTING_THRESHOLDS,
): LightingMetrics {
  if (!grid.length || !grid[0]?.length) {
    throw new Error("luminance grid must be non-empty");
  }
  const h = grid.length;
  const w = grid[0].length;
  const flat: number[] = [];
  for (const row of grid) {
    for (const v of row) flat.push(clamp01(v));
  }
  const meanLuminance = flat.reduce((a, b) => a + b, 0) / flat.length;
  const underexposedRatio =
    flat.filter((v) => v <= thresholds.lightUnderexposedLuma).length / flat.length;
  const overexposedRatio =
    flat.filter((v) => v >= thresholds.lightOverexposedLuma).length / flat.length;

  const magnitudes: number[] = [];
  let edges = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      let gx = 0;
      let gy = 0;
      for (let ky = 0; ky < 3; ky++) {
        for (let kx = 0; kx < 3; kx++) {
          const pixel = grid[y - 1 + ky][x - 1 + kx];
          gx += SOBEL_X[ky][kx] * pixel;
          gy += SOBEL_Y[ky][kx] * pixel;
        }
      }
      const mag = Math.sqrt(gx * gx + gy * gy) / SOBEL_MAX;
      magnitudes.push(mag);
      if (mag >= thresholds.sobelBinaryThreshold) edges += 1;
    }
  }
  magnitudes.sort((a, b) => a - b);
  const edgeDensity = magnitudes.length ? edges / magnitudes.length : 0;
  let percentileGradient = 0;
  if (magnitudes.length) {
    const pos = (thresholds.sharpnessGradientPercentile / 100) * (magnitudes.length - 1);
    const low = Math.floor(pos);
    const high = Math.min(low + 1, magnitudes.length - 1);
    const weight = pos - low;
    percentileGradient = magnitudes[low] * (1 - weight) + magnitudes[high] * weight;
  }
  const sharpnessScore = clamp01(
    percentileGradient / thresholds.sharpnessReferenceGradient,
  );

  const mid =
    (thresholds.lightUnderexposedLuma + thresholds.lightOverexposedLuma) / 2;
  const halfSpan = Math.max(
    1e-6,
    (thresholds.lightOverexposedLuma - thresholds.lightUnderexposedLuma) / 2,
  );
  const exposureCentering = clamp01(1 - Math.abs(meanLuminance - mid) / halfSpan);
  const clippingPenalty = clamp01(underexposedRatio + overexposedRatio);
  const lightQualityScore = clamp01(exposureCentering * (1 - clippingPenalty));

  const underexposed =
    meanLuminance <= thresholds.lightUnderexposedLuma ||
    underexposedRatio > thresholds.lightMaxClippedBlackRatio;
  const overexposed =
    meanLuminance >= thresholds.lightOverexposedLuma ||
    overexposedRatio > thresholds.lightMaxClippedWhiteRatio;
  const blurry = sharpnessScore < thresholds.sharpnessMinQuality;
  const lowEdgeDetail = edgeDensity < thresholds.sobelMinEdgeDensity;

  const flags: string[] = [];
  if (underexposed) flags.push("lighting_underexposed");
  if (overexposed) flags.push("lighting_overexposed");
  if (blurry) flags.push("image_blurry");
  if (lowEdgeDetail) flags.push("low_edge_detail");
  if (lightQualityScore < thresholds.lightMinQuality) {
    flags.push("lighting_below_min_quality");
  }

  return {
    meanLuminance,
    underexposedRatio,
    overexposedRatio,
    edgeDensity,
    sharpnessScore,
    lightQualityScore,
    underexposed,
    overexposed,
    blurry,
    lowEdgeDetail,
    flags,
  };
}

export function verdictFromMetrics(
  metrics: LightingMetrics,
  opts: {
    facePresent: boolean;
    nightVision?: boolean;
    thresholds?: LightingThresholds;
  },
): LightingReadiness {
  const nightVision = !!opts.nightVision;
  const thresholds =
    opts.thresholds ||
    (nightVision ? NIGHT_VISION_THRESHOLDS : DEFAULT_LIGHTING_THRESHOLDS);
  const facePresent = opts.facePresent;
  const tips: string[] = [];

  if (!facePresent) {
    return {
      verdict: "blocked_no_face",
      metrics,
      facePresent,
      nightVision,
      message:
        "Center your face in the frame and hold still until the check passes.",
      tips: ["Sit facing the camera", "Remove heavy shadows across your face"],
    };
  }

  // Night vision: allow dark rooms once a face is held, still block blown-out /
  // totally blurry frames that cannot support contours.
  if (nightVision) {
    if (metrics.overexposed) {
      return {
        verdict: "blocked_bright",
        metrics,
        facePresent,
        nightVision,
        message:
          "The image is washed out. Move away from strong backlight or reduce glare, then re-check.",
        tips: ["Face away from bright windows", "Lower screen brightness behind you"],
      };
    }
    if (metrics.blurry && metrics.lowEdgeDetail) {
      return {
        verdict: "blocked_blurry",
        metrics,
        facePresent,
        nightVision,
        message:
          "Center your face in the frame and hold still until the check passes.",
        tips: ["Wipe the lens", "Hold the device steady"],
      };
    }
    return {
      verdict: "ready",
      metrics,
      facePresent,
      nightVision,
      message: "Night vision on — lighting is low but your face is visible.",
      tips: [],
    };
  }

  const darkBlocked =
    metrics.underexposed ||
    (metrics.flags.includes("lighting_below_min_quality") &&
      metrics.meanLuminance < 0.35);
  if (darkBlocked) {
    const fixable =
      metrics.meanLuminance > 0.12 && metrics.lightQualityScore > 0.15;
    tips.push("Add a lamp or face a brighter area");
    tips.push("Avoid sitting with a bright window behind you");
    return {
      verdict: fixable ? "fixable" : "blocked_dark",
      metrics,
      facePresent,
      nightVision,
      message:
        "We cannot see you clearly. Add a lamp or face a brighter area, then re-check. Or enable Night vision if you must continue in low light.",
      tips,
    };
  }

  if (metrics.overexposed) {
    tips.push("Move away from strong backlight");
    tips.push("Reduce glare on your face");
    return {
      verdict: metrics.lightQualityScore > 0.2 ? "fixable" : "blocked_bright",
      metrics,
      facePresent,
      nightVision,
      message:
        "The image is washed out. Move away from strong backlight or reduce glare, then re-check.",
      tips,
    };
  }

  if (metrics.blurry || metrics.lowEdgeDetail) {
    tips.push("Hold still", "Move slightly closer so your face fills more of the frame");
    return {
      verdict: metrics.sharpnessScore > 0.15 ? "fixable" : "blocked_blurry",
      metrics,
      facePresent,
      nightVision,
      message:
        "Center your face in the frame and hold still until the check passes.",
      tips,
    };
  }

  if (metrics.flags.includes("lighting_below_min_quality")) {
    return {
      verdict: "fixable",
      metrics,
      facePresent,
      nightVision,
      message:
        "Lighting is borderline. We will try to auto-adjust; improve the room light if this keeps failing.",
      tips: ["Turn on a desk lamp aimed at your face"],
    };
  }

  return {
    verdict: "ready",
    metrics,
    facePresent,
    nightVision,
    message: "Camera and lighting look good — you can start class.",
    tips: [],
  };
}

/** Sample a video/image frame into a coarse luminance grid (default 64×36). */
export function luminanceGridFromImageData(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  gridW = 64,
  gridH = 36,
): number[][] {
  const rows: number[][] = [];
  for (let gy = 0; gy < gridH; gy++) {
    const row: number[] = [];
    const y0 = Math.floor((gy * height) / gridH);
    const y1 = Math.floor(((gy + 1) * height) / gridH);
    for (let gx = 0; gx < gridW; gx++) {
      const x0 = Math.floor((gx * width) / gridW);
      const x1 = Math.floor(((gx + 1) * width) / gridW);
      let sum = 0;
      let n = 0;
      for (let y = y0; y < Math.max(y0 + 1, y1); y++) {
        for (let x = x0; x < Math.max(x0 + 1, x1); x++) {
          const i = (y * width + x) * 4;
          sum += (0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]) / 255;
          n += 1;
        }
      }
      row.push(n ? sum / n : 0);
    }
    rows.push(row);
  }
  return rows;
}

/**
 * Best-effort continuous exposure / white-balance. Returns which keys were applied.
 * Never throws — unsupported devices simply get [].
 */
export async function tryApplyExposureConstraints(
  track: MediaStreamTrack,
): Promise<string[]> {
  const applied: string[] = [];
  const anyTrack = track as MediaStreamTrack & {
    getCapabilities?: () => Record<string, unknown>;
    applyConstraints?: (c: MediaTrackConstraints) => Promise<void>;
  };
  if (!anyTrack.getCapabilities || !anyTrack.applyConstraints) return applied;
  let caps: Record<string, unknown> = {};
  try {
    caps = anyTrack.getCapabilities() as unknown as Record<string, unknown>;
  } catch {
    return applied;
  }
  const advanced: Record<string, unknown> = {};
  if (caps.exposureMode && Array.isArray(caps.exposureMode) && caps.exposureMode.includes("continuous")) {
    advanced.exposureMode = "continuous";
  }
  if (caps.whiteBalanceMode && Array.isArray(caps.whiteBalanceMode) && caps.whiteBalanceMode.includes("continuous")) {
    advanced.whiteBalanceMode = "continuous";
  }
  if (typeof caps.exposureCompensation === "object" && caps.exposureCompensation) {
    const range = caps.exposureCompensation as { min?: number; max?: number };
    if (typeof range.max === "number" && range.max > 0) {
      advanced.exposureCompensation = Math.min(range.max, 0.5);
    }
  }
  if (typeof caps.brightness === "object" && caps.brightness) {
    const range = caps.brightness as { min?: number; max?: number };
    if (typeof range.min === "number" && typeof range.max === "number") {
      advanced.brightness = (range.min + range.max) / 2;
    }
  }
  if (!Object.keys(advanced).length) return applied;
  try {
    await anyTrack.applyConstraints({ advanced: [advanced as MediaTrackConstraintSet] });
    applied.push(...Object.keys(advanced));
  } catch {
    try {
      await anyTrack.applyConstraints(advanced as MediaTrackConstraints);
      applied.push(...Object.keys(advanced));
    } catch {
      /* device rejected — fail closed at the verdict layer */
    }
  }
  return applied;
}

export function isLightingReady(verdict: LightingVerdict): boolean {
  return verdict === "ready";
}

/**
 * The 8-expression contract shared across the mascot pipeline.
 *
 * Shipping expressions on a sculpted stone statue is a special case:
 * we can't swap a baked face with a Canvas2D sticker without wrecking
 * the stone aesthetic, and we can't deform the mesh without a rig.
 * Instead each expression maps to a MoodProfile (color tint, head /
 * body posture angle, particle overlay, scale pulse) that MascotMeshy
 * applies to the loaded glTF scene.
 *
 * These names/labels pre-date the mood-overlay approach and used to
 * drive a Canvas2D face plane. The 2D face plane was deleted when we
 * switched to the real Meshy mesh.
 */

export const EXPRESSION_NAMES = [
  "cute",
  "serious",
  "angry",
  "sad",
  "crying",
  "excited",
  "curious",
  "mischievous",
] as const;

export type Expression = (typeof EXPRESSION_NAMES)[number];

/** Human-readable copy for the lab UI picker. */
export const EXPRESSION_LABELS: Record<Expression, string> = {
  cute: "Cute (default — warm neutral)",
  serious: "Serious (calm, cool tone, upright)",
  angry: "Angry (warm red tint, puffed, heat shimmer)",
  sad: "Sad (cool blue tint, hunched forward)",
  crying: "Crying (cool desaturated, falling tears)",
  excited: "Excited (gold tint, bounce, sparkles)",
  curious: "Curious (body tilts right)",
  mischievous: "Mischievous (body tilts left, warm tint)",
};

/** Which expression best fits a given MascotScene kind, used when the
 *  renderer wants a sensible default (lab page lets the user override). */
export function expressionForSceneKind(kind: string | undefined): Expression {
  switch (kind) {
    case "flyin-point":
    case "dance":
    case "video":
      return "excited";
    case "teacher":
    case "presentation":
      return "serious";
    case "reading":
      return "curious";
    case "gaming":
      return "mischievous";
    case "age-morph":
    case "tutoring":
    case "idle":
    default:
      return "cute";
  }
}

/**
 * How each expression should look on the Meshy mesh. The renderer
 * reads this to tint materials, add particle overlays, and change the
 * body's resting pose. Values are intentionally subtle - stone statues
 * do not grimace, so we lean on tone + particles + posture rather
 * than facial deformation.
 */
export interface MoodProfile {
  /** Additive emissive tint applied to every mesh material. 0,0,0 = none. */
  emissive: readonly [number, number, number];
  /** Multiplier for the emissive tint intensity. */
  emissiveIntensity: number;
  /** Body yaw tilt in radians (positive = tilt right from viewer). */
  bodyTiltZ: number;
  /** Body forward lean in radians (positive = lean forward). */
  bodyLeanX: number;
  /** Body scale pulse frequency in Hz (0 = no pulse). */
  pulseHz: number;
  /** Body scale pulse amplitude (0 = no pulse, 0.05 = +/- 5%). */
  pulseAmp: number;
  /** Which particle overlay to render above/around the body. */
  particles: "none" | "tears" | "sparkles" | "shimmer";
}

export const MOOD_PROFILES: Record<Expression, MoodProfile> = {
  cute: {
    emissive: [0.0, 0.0, 0.0],
    emissiveIntensity: 0,
    bodyTiltZ: 0,
    bodyLeanX: 0,
    pulseHz: 0,
    pulseAmp: 0,
    particles: "none",
  },
  serious: {
    // Faint cool neutral - a touch of distance.
    emissive: [0.05, 0.07, 0.1],
    emissiveIntensity: 0.25,
    bodyTiltZ: 0,
    bodyLeanX: -0.05,
    pulseHz: 0,
    pulseAmp: 0,
    particles: "none",
  },
  angry: {
    // Warm red glow + puffed-up pulse + heat shimmer.
    emissive: [0.55, 0.1, 0.05],
    emissiveIntensity: 0.4,
    bodyTiltZ: 0,
    bodyLeanX: 0.05,
    pulseHz: 2.5,
    pulseAmp: 0.03,
    particles: "shimmer",
  },
  sad: {
    // Cool blue tint + forward hunch, no particles.
    emissive: [0.05, 0.1, 0.3],
    emissiveIntensity: 0.3,
    bodyTiltZ: 0,
    bodyLeanX: 0.18,
    pulseHz: 0,
    pulseAmp: 0,
    particles: "none",
  },
  crying: {
    // Even cooler + falling tears.
    emissive: [0.05, 0.15, 0.35],
    emissiveIntensity: 0.4,
    bodyTiltZ: 0,
    bodyLeanX: 0.2,
    pulseHz: 1.5,
    pulseAmp: 0.012,
    particles: "tears",
  },
  excited: {
    // Warm gold + visible bounce + sparkles.
    emissive: [0.5, 0.35, 0.1],
    emissiveIntensity: 0.5,
    bodyTiltZ: 0,
    bodyLeanX: -0.08,
    pulseHz: 4,
    pulseAmp: 0.05,
    particles: "sparkles",
  },
  curious: {
    // Mild warm + body tilts right.
    emissive: [0.15, 0.12, 0.08],
    emissiveIntensity: 0.25,
    bodyTiltZ: 0.18,
    bodyLeanX: 0,
    pulseHz: 0,
    pulseAmp: 0,
    particles: "none",
  },
  mischievous: {
    // Warm + body tilts left + small sparkle.
    emissive: [0.3, 0.2, 0.05],
    emissiveIntensity: 0.35,
    bodyTiltZ: -0.18,
    bodyLeanX: 0,
    pulseHz: 1.2,
    pulseAmp: 0.015,
    particles: "sparkles",
  },
};

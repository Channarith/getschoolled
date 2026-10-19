"use client";

/**
 * Procedural face textures for the Salareen "Bayon Buddy" mascot.
 *
 * The face is a Canvas2D drawing (eyes, brows, mouth, cheeks, optional
 * tears / sparkles) rendered to a THREE.CanvasTexture. The texture is
 * then applied to a flat Plane sitting a hair in front of the 3D head
 * sphere, so a cartoon face reads correctly from any camera angle.
 *
 * Why Canvas2D instead of real 3D morph targets:
 *   - Zero authoring work. No Blender, no shape keys, no .glb export.
 *   - 8 expressions = 8 small Canvas2D draw functions, hot-swappable at
 *     runtime by regenerating the texture (<2 ms per expression).
 *   - Reads beautifully for a cartoon mascot — real anime/cartoon faces
 *     are literally drawn 2D over a 3D head in production games too.
 *
 * To add a 9th expression:
 *   1. Add it to EXPRESSION_NAMES below.
 *   2. Add a case in drawExpression() returning the eye/brow/mouth state.
 *   3. Done. The lab page's picker will show it automatically.
 */

import * as THREE from "three";

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
  cute: "Cute (default — happy closed-eye smile)",
  serious: "Serious (open eyes, calm neutral)",
  angry: "Angry (furrowed brow, tight frown)",
  sad: "Sad (drooping brow, downturned mouth)",
  crying: "Crying (closed eyes + tear drops)",
  excited: "Excited (wide eyes, big smile, sparkles)",
  curious: "Curious (one brow raised, side-eye)",
  mischievous: "Mischievous (half-lidded smirk)",
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

const TEXTURE_SIZE = 512;
const SKIN = "#d8b48a";        // light sandstone face plate
const INK = "#2a1d12";         // dark warm brown for lines + pupils
const BLUSH = "#e18a7a";       // soft rose cheek
const TEAR = "#7fcff2";        // pale blue tear drop
const SPARKLE = "#fff7cf";     // warm cream highlight

type FaceState = {
  /** Horizontal position of eye centres (0..1 of canvas width). */
  eyeY: number;
  /** How open the eyes are (0 = closed arc, 1 = round, 2 = wide). */
  eyeOpen: number;
  /** Horizontal squeeze for squinted eyes (1 = round, 2 = oval). */
  eyeSquint: number;
  /** Brow angle in radians (negative = inner-down/angry, positive = inner-up/sad). */
  browAngle: number;
  /** Brow lift (how high above the eye). */
  browLift: number;
  /** Mouth: -1 = frown, 0 = neutral, +1 = smile. */
  mouthCurve: number;
  /** Mouth width (small -> big). */
  mouthWidth: number;
  /** Mouth openness (0 = closed line, 1 = open circle). */
  mouthOpen: number;
  /** Smirk: +1 = right corner up, -1 = left corner up, 0 = symmetric. */
  mouthAsymmetry: number;
  /** 0 = no blush, 1 = bright rose cheeks. */
  blush: number;
  /** True = draw tear drops. */
  tears: boolean;
  /** True = draw sparkle glints near eyes. */
  sparkles: boolean;
};

function stateFor(expr: Expression): FaceState {
  switch (expr) {
    case "cute":
      return { eyeY: 0.42, eyeOpen: 0, eyeSquint: 1, browAngle: 0, browLift: 0.07,
               mouthCurve: 1, mouthWidth: 0.26, mouthOpen: 0, mouthAsymmetry: 0,
               blush: 0.7, tears: false, sparkles: false };
    case "serious":
      return { eyeY: 0.42, eyeOpen: 1, eyeSquint: 1, browAngle: 0, browLift: 0.09,
               mouthCurve: 0, mouthWidth: 0.22, mouthOpen: 0, mouthAsymmetry: 0,
               blush: 0, tears: false, sparkles: false };
    case "angry":
      return { eyeY: 0.42, eyeOpen: 0.9, eyeSquint: 1.4, browAngle: -0.6, browLift: 0.05,
               mouthCurve: -0.7, mouthWidth: 0.22, mouthOpen: 0, mouthAsymmetry: 0,
               blush: 0.3, tears: false, sparkles: false };
    case "sad":
      return { eyeY: 0.44, eyeOpen: 0.7, eyeSquint: 1, browAngle: 0.5, browLift: 0.08,
               mouthCurve: -0.8, mouthWidth: 0.22, mouthOpen: 0, mouthAsymmetry: 0,
               blush: 0, tears: false, sparkles: false };
    case "crying":
      return { eyeY: 0.42, eyeOpen: 0, eyeSquint: 1, browAngle: 0.4, browLift: 0.08,
               mouthCurve: -0.9, mouthWidth: 0.26, mouthOpen: 0.35, mouthAsymmetry: 0,
               blush: 0.2, tears: true, sparkles: false };
    case "excited":
      return { eyeY: 0.4, eyeOpen: 1.7, eyeSquint: 1, browAngle: 0, browLift: 0.14,
               mouthCurve: 1, mouthWidth: 0.32, mouthOpen: 0.4, mouthAsymmetry: 0,
               blush: 0.6, tears: false, sparkles: true };
    case "curious":
      return { eyeY: 0.42, eyeOpen: 1.1, eyeSquint: 1, browAngle: 0, browLift: 0.09,
               mouthCurve: 0.3, mouthWidth: 0.2, mouthOpen: 0.1, mouthAsymmetry: 0.4,
               blush: 0, tears: false, sparkles: false };
    case "mischievous":
      return { eyeY: 0.44, eyeOpen: 0.5, eyeSquint: 1.3, browAngle: -0.2, browLift: 0.08,
               mouthCurve: 0.8, mouthWidth: 0.26, mouthOpen: 0, mouthAsymmetry: 0.7,
               blush: 0.3, tears: false, sparkles: false };
  }
}

function drawFacePlate(ctx: CanvasRenderingContext2D): void {
  // Soft oval face plate - the texture ultimately sits on a plane in front
  // of the head sphere, with alpha outside the oval so we see the 3D head.
  const w = TEXTURE_SIZE;
  const h = TEXTURE_SIZE;
  ctx.clearRect(0, 0, w, h);
  const grd = ctx.createRadialGradient(w / 2, h / 2, w * 0.1, w / 2, h / 2, w * 0.5);
  grd.addColorStop(0, SKIN);
  grd.addColorStop(0.75, SKIN);
  grd.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = grd;
  ctx.beginPath();
  ctx.ellipse(w / 2, h / 2, w * 0.46, h * 0.48, 0, 0, Math.PI * 2);
  ctx.fill();
}

function drawEye(ctx: CanvasRenderingContext2D, cx: number, cy: number,
                 state: FaceState, mirror: boolean): void {
  ctx.save();
  ctx.strokeStyle = INK;
  ctx.fillStyle = INK;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  const r = 36;

  if (state.eyeOpen <= 0.05) {
    // Closed happy arc (smiling eye). The arc curves UP in canvas coords
    // (lower y) to read as "happy", not "sad closed".
    ctx.lineWidth = 10;
    ctx.beginPath();
    ctx.arc(cx, cy + 6, r * 0.9, Math.PI, 0, false);
    ctx.stroke();
  } else {
    // Open eye: filled oval pupil over white sclera.
    const rx = r * state.eyeOpen;
    const ry = r * state.eyeOpen * state.eyeSquint;
    ctx.fillStyle = "#f7eedd";       // warm cream sclera
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry * 0.85, 0, 0, Math.PI * 2);
    ctx.fill();
    // Pupil - slightly off-centre toward where the character looks.
    const look = mirror ? -4 : 4;
    ctx.fillStyle = INK;
    const pupilR = Math.min(rx, ry) * 0.6;
    ctx.beginPath();
    ctx.arc(cx + look, cy + 2, pupilR, 0, Math.PI * 2);
    ctx.fill();
    // Glint highlight for liveness.
    ctx.fillStyle = SPARKLE;
    ctx.beginPath();
    ctx.arc(cx + look - pupilR * 0.35, cy - pupilR * 0.35,
            Math.max(3, pupilR * 0.25), 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawBrow(ctx: CanvasRenderingContext2D, cx: number, cy: number,
                  state: FaceState, mirror: boolean): void {
  // Brow is a short thick line above the eye. browAngle rotates it around
  // its outer end so negative = angry V, positive = sad slope.
  ctx.save();
  ctx.strokeStyle = INK;
  ctx.lineWidth = 11;
  ctx.lineCap = "round";
  const sign = mirror ? -1 : 1;
  const browY = cy - 50 - state.browLift * 100;
  const length = 60;
  const angle = sign * state.browAngle;
  const dx = Math.cos(angle) * length;
  const dy = Math.sin(angle) * length;
  ctx.beginPath();
  ctx.moveTo(cx - sign * dx / 2, browY - dy / 2);
  ctx.lineTo(cx + sign * dx / 2, browY + dy / 2);
  ctx.stroke();
  ctx.restore();
}

function drawMouth(ctx: CanvasRenderingContext2D, state: FaceState): void {
  const cx = TEXTURE_SIZE / 2;
  const cy = TEXTURE_SIZE * 0.66;
  const w = TEXTURE_SIZE * state.mouthWidth;
  ctx.save();
  ctx.strokeStyle = INK;
  ctx.fillStyle = INK;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = 10;

  if (state.mouthOpen > 0.05) {
    // Open mouth: filled dark oval with a slight curve top/bottom.
    const openH = 30 + state.mouthOpen * 40;
    ctx.beginPath();
    ctx.ellipse(cx + state.mouthAsymmetry * 10, cy,
                w / 2, openH / 2, 0, 0, Math.PI * 2);
    ctx.fill();
    // Soft smile line above for excited open-mouth.
    if (state.mouthCurve > 0) {
      ctx.beginPath();
      ctx.moveTo(cx - w / 2, cy - openH / 2);
      ctx.quadraticCurveTo(cx, cy - openH / 2 - 16 * state.mouthCurve,
                           cx + w / 2, cy - openH / 2);
      ctx.stroke();
    }
  } else {
    // Closed mouth: curve. mouthCurve controls lift at ends.
    const lift = state.mouthCurve * 22;
    const asym = state.mouthAsymmetry * 14;
    ctx.beginPath();
    ctx.moveTo(cx - w / 2, cy - lift / 2 - asym);
    ctx.quadraticCurveTo(cx, cy + lift / 2,
                         cx + w / 2, cy - lift / 2 + asym);
    ctx.stroke();
  }
  ctx.restore();
}

function drawBlush(ctx: CanvasRenderingContext2D, intensity: number): void {
  if (intensity <= 0) return;
  ctx.save();
  ctx.globalAlpha = intensity * 0.55;
  ctx.fillStyle = BLUSH;
  const cy = TEXTURE_SIZE * 0.56;
  for (const sign of [-1, 1]) {
    ctx.beginPath();
    ctx.ellipse(TEXTURE_SIZE / 2 + sign * TEXTURE_SIZE * 0.22,
                cy, 36, 22, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawTears(ctx: CanvasRenderingContext2D): void {
  ctx.save();
  ctx.fillStyle = TEAR;
  const cy = TEXTURE_SIZE * 0.42;
  for (const sign of [-1, 1]) {
    const cx = TEXTURE_SIZE / 2 + sign * TEXTURE_SIZE * 0.18;
    // Tear drop: a filled teardrop shape (circle + triangle).
    ctx.beginPath();
    ctx.arc(cx, cy + 60, 16, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(cx - 14, cy + 60);
    ctx.lineTo(cx, cy + 20);
    ctx.lineTo(cx + 14, cy + 60);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
}

function drawSparkles(ctx: CanvasRenderingContext2D): void {
  ctx.save();
  ctx.fillStyle = SPARKLE;
  for (const [x, y, r] of [[0.22, 0.3, 8], [0.78, 0.3, 8],
                            [0.14, 0.42, 5], [0.86, 0.42, 5]] as const) {
    ctx.beginPath();
    ctx.arc(TEXTURE_SIZE * x, TEXTURE_SIZE * y, r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/**
 * Build a THREE.CanvasTexture for the given expression. Cheap enough to
 * regenerate on every expression swap (<2 ms on a laptop).
 */
export function expressionTexture(expr: Expression): THREE.CanvasTexture {
  if (typeof document === "undefined") {
    // SSR guard - any R3F component importing this is already client-only,
    // but keep this defensive so prerender can't crash on canvas access.
    throw new Error("expressionTexture() must be called in the browser");
  }
  const canvas = document.createElement("canvas");
  canvas.width = TEXTURE_SIZE;
  canvas.height = TEXTURE_SIZE;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("could not get 2D canvas context");

  const state = stateFor(expr);

  drawFacePlate(ctx);
  drawBlush(ctx, state.blush);

  const eyeOffsetX = TEXTURE_SIZE * 0.18;
  const eyeY = TEXTURE_SIZE * state.eyeY;
  const cx = TEXTURE_SIZE / 2;
  drawEye(ctx, cx - eyeOffsetX, eyeY, state, true);
  drawEye(ctx, cx + eyeOffsetX, eyeY, state, false);
  drawBrow(ctx, cx - eyeOffsetX, eyeY, state, true);
  drawBrow(ctx, cx + eyeOffsetX, eyeY, state, false);
  drawMouth(ctx, state);
  if (state.tears) drawTears(ctx);
  if (state.sparkles) drawSparkles(ctx);

  const tex = new THREE.CanvasTexture(canvas);
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  return tex;
}

/** Dispose of a texture produced by expressionTexture(). Call before
 *  replacing with a fresh one to free the GPU-side allocation. */
export function disposeExpressionTexture(tex: THREE.Texture | null): void {
  if (!tex) return;
  tex.dispose();
}

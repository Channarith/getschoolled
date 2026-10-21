"use client";

/**
 * MascotMeshy — real Meshy.ai-generated Bayon Buddy mascot with REAL
 * rigged animation playback, mood overlays, and an idle rotation for
 * waiting moments in the setup assistant.
 *
 * The character is apps/web/public/mascot3d/Mascot.glb (produced from
 * the user's Meshy "All Animations" export, slimmed via
 * scripts/mascot_meshy_prep.py from 124 MB -> 3.1 MB). It ships with:
 *
 *   - A real skeleton (1 skin) and 15 named animation clips produced
 *     by Meshy's rigging + Mixamo retargeting pipeline:
 *       Walking, Running, Confident_Strut, Big_Wave_Hello,
 *       Wave_for_Help_1, Wave_for_Help_2, Indoor_Swing, Boom_Dance,
 *       _360_Power_Spin_Jump, Jump_Rope, Boxing_Practice,
 *       Breakdance_1990, Step_in_High_Kick, One_Arm_Handstand,
 *       Thrust_Slash
 *   - Baked PBR textures at 512x512 (base color + normal + metallic/
 *     roughness) with Draco mesh compression.
 *
 * This component plays those real clips via drei's useAnimations (no
 * fake hop + lean anymore - the character's legs actually bend) and
 * layers mood overlays on top (emissive tint, particles, scale pulse)
 * for expression without wrecking the sculpted stone aesthetic.
 *
 * Three ways to drive it from props:
 *   - motion="idle" | "walk" | "run"  (default routing to one clip)
 *   - clip=<specific clip name>       (override, lab uses this)
 *   - idleRotation=true (when motion==="idle", cycles through a
 *     curated calm/charming subset every ~5s - perfect for the setup
 *     assistant's wait moments)
 */

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  OrbitControls,
  useAnimations,
  useGLTF,
} from "@react-three/drei";
import * as THREE from "three";
// SkeletonUtils.clone performs a DEEP clone that correctly rebinds every
// SkinnedMesh's `.skeleton` to the cloned bones. Plain `scene.clone(true)`
// clones the meshes and the bones but leaves `.skeleton` pointing at the
// ORIGINAL bones - so the AnimationMixer updates the cloned bones but the
// mesh renders using the un-updated originals and NOTHING MOVES. This is
// the standard three.js footgun for skinned-mesh cloning.
import { clone as cloneWithSkeleton } from "three/examples/jsm/utils/SkeletonUtils.js";

import {
  type Expression,
  MOOD_PROFILES,
  type MoodProfile,
} from "./mascot3d/expressions";

const MODEL_URL = "/mascot3d/Mascot.glb";
const DRACO_DECODER = "/mascot3d/draco/";

/**
 * Every animation clip baked into the current Mascot.glb. Pinned to
 * what the Meshy "All Animations" pack shipped. If you re-run the prep
 * script on a different Meshy export, re-generate this list from the
 * validator output and the lab page's clip picker will update
 * automatically.
 */
export const CLIP_NAMES = [
  "_360_Power_Spin_Jump",
  "Big_Wave_Hello",
  "Boom_Dance",
  "Boxing_Practice",
  "Breakdance_1990",
  "Confident_Strut",
  "Indoor_Swing",
  "Jump_Rope",
  "One_Arm_Handstand",
  "Running",
  "Step_in_High_Kick",
  "Thrust_Slash",
  "Walking",
  "Wave_for_Help_1",
  "Wave_for_Help_2",
] as const;
export type ClipName = (typeof CLIP_NAMES)[number];

export type MotionState = "idle" | "walk" | "run";

/** Default clip for each motion state. "idle" picks a friendly wave so
 *  a static character still reads as alive; the idle rotation (below)
 *  cycles beyond that first wave when enabled. */
export const MOTION_TO_CLIP: Record<MotionState, ClipName> = {
  idle: "Big_Wave_Hello",
  walk: "Walking",
  run: "Running",
};

/**
 * Family-friendly rotation of calm / charming idles for the setup
 * assistant's wait moments. Deliberately skips the aggressive /
 * showoff clips (Boxing_Practice, Breakdance_1990, Thrust_Slash,
 * One_Arm_Handstand, Step_in_High_Kick) since this is an education
 * mascot and those read as "mascot is going to fight you" rather than
 * "cute statue is being patient while you set up".
 */
export const IDLE_ROTATION: ClipName[] = [
  "Big_Wave_Hello",
  "Confident_Strut",
  "Indoor_Swing",
  "Boom_Dance",
  "Wave_for_Help_1",
  "Jump_Rope",
  "_360_Power_Spin_Jump",
  "Wave_for_Help_2",
];

type Props = {
  /** Current facial / mood expression. Hot-swappable. */
  expression: Expression;
  /** Optional motion state. Ignored if `clip` is provided. */
  motion?: MotionState;
  /** Override: play this specific clip (used by the lab clip picker). */
  clip?: ClipName;
  /**
   * When true AND motion === "idle" AND clip is not provided, cycle
   * through IDLE_ROTATION every `rotationIntervalMs` to keep the
   * waiting character interesting. The setup assistant turns this on.
   */
  idleRotation?: boolean;
  /** Default 5000 ms per clip when idleRotation is on. */
  rotationIntervalMs?: number;
  /** Pixel size of the canvas (square). Default 480. Ignored when `fill`. */
  size?: number;
  /** When true, fill the parent container instead of a fixed square. Use
   *  this when slotting the mascot into a flexibly-sized layout (e.g.
   *  the setup assistant's right pane). */
  fill?: boolean;
  className?: string;
  /** True = show mouse-drag orbit controls (handy in the lab, off in prod). */
  interactive?: boolean;
  /** Clear canvas so the mesh sits on the setup-assistant stage. */
  transparent?: boolean;
  /** Solid stage color behind the mesh. Wins over `transparent`. */
  backdrop?: string;
  /** Stop the render loop without destroying the WebGL canvas. */
  paused?: boolean;
  /** Keep the darkened stone from the voice-check page. Expression still
   *  changes posture and motion, but not the bronze color. */
  holdStone?: boolean;
};

/* ---------------------------------------------------------------------
 * Mood overlay helpers (unchanged from the pre-animation version — the
 * emissive tint, particle sprites, and scale pulse are all orthogonal
 * to glTF skeletal animation and still read correctly on top of it).
 * ------------------------------------------------------------------- */

/** Any material that exposes an `.emissive` color field - covers
 *  MeshStandardMaterial, MeshPhysicalMaterial, and MeshLambertMaterial,
 *  which are all possible outputs from Meshy / glTF loaders. */
type EmissiveMaterial = THREE.Material & {
  emissive: THREE.Color;
  emissiveIntensity: number;
  needsUpdate: boolean;
};

function isEmissive(m: THREE.Material | undefined | null): m is EmissiveMaterial {
  return !!m && (m as EmissiveMaterial).emissive instanceof THREE.Color;
}

type OriginalEmissive = {
  mat: EmissiveMaterial;
  color: THREE.Color;
  intensity: number;
};
function snapshotEmissives(root: THREE.Object3D): OriginalEmissive[] {
  const snaps: OriginalEmissive[] = [];
  const seen = new Set<string>();
  root.traverse((obj) => {
    // Covers both Mesh and SkinnedMesh.
    const anyObj = obj as THREE.Mesh;
    if (!("material" in anyObj) || !anyObj.material) return;
    const mats = Array.isArray(anyObj.material) ? anyObj.material : [anyObj.material];
    for (const m of mats) {
      if (!isEmissive(m)) continue;
      if (seen.has(m.uuid)) continue; // Meshy often reuses one material across submeshes.
      seen.add(m.uuid);
      snaps.push({
        mat: m,
        color: m.emissive.clone(),
        intensity: m.emissiveIntensity ?? 1,
      });
    }
  });
  return snaps;
}

function contrastByte(value: number): number {
  return value < 0 ? 0 : value > 255 ? 255 : Math.round(value);
}

/**
 * Ease the baked stone down without posterizing it. A hard stretch
 * turned the sandstone into noisy blocks and made the atlas gaps read
 * as holes. Eyes stay darker than the gold; the rest stays one material.
 */
function gradeStoneByte(value: number): number {
  const darkened = value * 0.88;
  const curved = (darkened - 120) * 1.12 + 120;
  // A texel at 0 is an atlas gap. The mesh samples it and the stage
  // shows through. Keep a floor so carved shadows stay brown, not holes.
  return contrastByte(curved < 22 ? 22 : curved);
}

/**
 * The albedo is a UV atlas. The gaps between islands are pure black, and
 * the mesh samples them, so the stage shows through as pixelated holes.
 * Paint each black texel with the nearest stone color. Dark features
 * such as the eyes sit above this cutoff and stay put.
 */
function sealAtlasHoles(data: Uint8ClampedArray, width: number, height: number): void {
  const count = width * height;
  const hole = new Uint8Array(count);
  for (let p = 0, i = 0; p < count; p += 1, i += 4) {
    const max = data[i] > data[i + 1]
      ? (data[i] > data[i + 2] ? data[i] : data[i + 2])
      : (data[i + 1] > data[i + 2] ? data[i + 1] : data[i + 2]);
    hole[p] = max < 8 ? 1 : 0;
  }
  const qx = new Int32Array(count);
  const qy = new Int32Array(count);
  const color = new Uint8Array(count * 3);
  const filled = new Uint8Array(count);
  let tail = 0;
  const push = (x: number, y: number, r: number, g: number, b: number) => {
    const p = y * width + x;
    if (!hole[p] || filled[p]) return;
    filled[p] = 1;
    const o = p * 3;
    color[o] = r;
    color[o + 1] = g;
    color[o + 2] = b;
    qx[tail] = x;
    qy[tail] = y;
    tail += 1;
  };
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const p = y * width + x;
      if (hole[p]) continue;
      const i = p * 4;
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      if (x > 0) push(x - 1, y, r, g, b);
      if (x + 1 < width) push(x + 1, y, r, g, b);
      if (y > 0) push(x, y - 1, r, g, b);
      if (y + 1 < height) push(x, y + 1, r, g, b);
    }
  }
  let head = 0;
  while (head < tail) {
    const x = qx[head];
    const y = qy[head];
    head += 1;
    const o = (y * width + x) * 3;
    const r = color[o];
    const g = color[o + 1];
    const b = color[o + 2];
    if (x > 0) push(x - 1, y, r, g, b);
    if (x + 1 < width) push(x + 1, y, r, g, b);
    if (y > 0) push(x, y - 1, r, g, b);
    if (y + 1 < height) push(x, y + 1, r, g, b);
  }
  for (let p = 0; p < count; p += 1) {
    if (!filled[p]) continue;
    const i = p * 4;
    const o = p * 3;
    data[i] = color[o];
    data[i + 1] = color[o + 1];
    data[i + 2] = color[o + 2];
  }
  // The gap has a dark brown halo. Two passes pull that fringe in so
  // linear filtering cannot pick it back up. Eyes sit inside the face
  // island, away from the gaps, so they are not painted over.
  for (let pass = 0; pass < 2; pass += 1) {
    const extra: number[] = [];
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const p = y * width + x;
        if (!filled[p]) continue;
        const i = p * 4;
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const around = [
          x > 0 ? p - 1 : -1,
          x + 1 < width ? p + 1 : -1,
          y > 0 ? p - width : -1,
          y + 1 < height ? p + width : -1,
        ];
        for (const n of around) {
          if (n < 0 || filled[n]) continue;
          const j = n * 4;
          const max = data[j] > data[j + 1]
            ? (data[j] > data[j + 2] ? data[j] : data[j + 2])
            : (data[j + 1] > data[j + 2] ? data[j + 1] : data[j + 2]);
          if (max < 48) extra.push(n, r, g, b);
        }
      }
    }
    for (let k = 0; k < extra.length; k += 4) {
      const n = extra[k];
      if (filled[n]) continue;
      filled[n] = 1;
      const j = n * 4;
      data[j] = extra[k + 1];
      data[j + 1] = extra[k + 2];
      data[j + 2] = extra[k + 3];
    }
  }
}

function contrastSource(
  source: CanvasImageSource,
  width: number,
  height: number,
): HTMLCanvasElement | null {
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(source, 0, 0, width, height);
  const image = ctx.getImageData(0, 0, width, height);
  const data = image.data;
  sealAtlasHoles(data, width, height);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = gradeStoneByte(data[i]);
    data[i + 1] = gradeStoneByte(data[i + 1]);
    data[i + 2] = gradeStoneByte(data[i + 2]);
  }
  ctx.putImageData(image, 0, 0);
  // The baked map is 512px and was sampled with nearest filtering, so the
  // stone broke into squares. Draw it at 2x with smoothing before the GPU
  // magnifies it again.
  const smooth = document.createElement("canvas");
  smooth.width = width * 2;
  smooth.height = height * 2;
  const smoothCtx = smooth.getContext("2d");
  if (!smoothCtx) return canvas;
  smoothCtx.imageSmoothingEnabled = true;
  smoothCtx.imageSmoothingQuality = "high";
  smoothCtx.drawImage(canvas, 0, 0, smooth.width, smooth.height);
  return smooth;
}

function smoothTexture(map: THREE.Texture, anisotropy: number): void {
  map.magFilter = THREE.LinearFilter;
  map.minFilter = THREE.LinearMipmapLinearFilter;
  map.generateMipmaps = true;
  map.anisotropy = anisotropy;
  map.needsUpdate = true;
}

function clarifyStoneMesh(root: THREE.Object3D): void {
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.material) return;
    const sourceMats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const mats = sourceMats.map((mat) => mat.clone());
    mesh.material = Array.isArray(mesh.material) ? mats : mats[0];
    for (const mat of mats) {
      const standard = mat as THREE.MeshStandardMaterial;
      if (!standard.isMeshStandardMaterial) continue;
      // The metallic map turns the face into a dark mirror. Keep a little
      // metal and let the base color carry the features.
      standard.metalness = Math.min(standard.metalness ?? 1, 0.08);
      if ((standard.roughness ?? 1) < 0.72) standard.roughness = 0.72;
      standard.envMapIntensity = 0.12;
      standard.transparent = false;
      standard.alphaTest = 0;
      standard.depthWrite = true;
      if (standard.normalScale) standard.normalScale.set(0.45, 0.45);
      const anisotropy = 8;
      for (const tex of [standard.normalMap, standard.roughnessMap, standard.metalnessMap, standard.aoMap]) {
        if (tex) smoothTexture(tex, anisotropy);
      }
      const map = standard.map;
      const image = map?.image as (CanvasImageSource & { width?: number; height?: number }) | undefined;
      if (map && image?.width && image.height) {
        try {
          const boosted = contrastSource(image, image.width, image.height);
          if (boosted) {
            standard.map = map.clone();
            standard.map.image = boosted;
            standard.map.colorSpace = THREE.SRGBColorSpace;
            smoothTexture(standard.map, anisotropy);
          } else {
            smoothTexture(map, anisotropy);
          }
        } catch {
          smoothTexture(map, anisotropy);
        }
      }
      standard.needsUpdate = true;
    }
  });
}

function applyMoodTint(snaps: OriginalEmissive[], mood: MoodProfile): void {
  for (const s of snaps) {
    s.mat.emissive.copy(s.color).add(
      new THREE.Color(mood.emissive[0], mood.emissive[1], mood.emissive[2]),
    );
    // Multiplicative boost on top of the material's baseline so moods
    // read even through a heavily-textured PBR base color.
    s.mat.emissiveIntensity = (s.intensity || 1) + mood.emissiveIntensity;
    s.mat.needsUpdate = true;
  }
}

function makeParticleTexture(
  kind: "tears" | "sparkles" | "shimmer",
): THREE.CanvasTexture {
  const SIZE = 128;
  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, SIZE, SIZE);
  if (kind === "tears") {
    ctx.fillStyle = "rgba(140, 210, 240, 0.9)";
    ctx.beginPath();
    ctx.arc(SIZE / 2, SIZE * 0.65, SIZE * 0.22, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(SIZE / 2 - SIZE * 0.2, SIZE * 0.65);
    ctx.lineTo(SIZE / 2, SIZE * 0.15);
    ctx.lineTo(SIZE / 2 + SIZE * 0.2, SIZE * 0.65);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.75)";
    ctx.beginPath();
    ctx.arc(SIZE / 2 - SIZE * 0.08, SIZE * 0.6, SIZE * 0.06, 0, Math.PI * 2);
    ctx.fill();
  } else if (kind === "sparkles") {
    ctx.fillStyle = "rgba(255, 220, 110, 0.95)";
    ctx.beginPath();
    for (let i = 0; i < 8; i++) {
      const angle = (i / 8) * Math.PI * 2;
      const r = i % 2 === 0 ? SIZE * 0.42 : SIZE * 0.14;
      const x = SIZE / 2 + Math.cos(angle) * r;
      const y = SIZE / 2 + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
    const grd = ctx.createRadialGradient(SIZE / 2, SIZE / 2, 0, SIZE / 2, SIZE / 2, SIZE / 2);
    grd.addColorStop(0, "rgba(255,240,180,0.5)");
    grd.addColorStop(1, "rgba(255,240,180,0)");
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, SIZE, SIZE);
  } else {
    const grd = ctx.createRadialGradient(SIZE / 2, SIZE / 2, 0, SIZE / 2, SIZE / 2, SIZE / 2);
    grd.addColorStop(0, "rgba(255,140,70,0.6)");
    grd.addColorStop(0.5, "rgba(255,80,40,0.25)");
    grd.addColorStop(1, "rgba(255,80,40,0)");
    ctx.fillStyle = grd;
    ctx.beginPath();
    ctx.ellipse(SIZE / 2, SIZE / 2, SIZE * 0.45, SIZE * 0.35, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

const PARTICLE_TEX_CACHE: Partial<Record<"tears" | "sparkles" | "shimmer", THREE.CanvasTexture>> = {};
function particleTextureFor(kind: "tears" | "sparkles" | "shimmer"): THREE.CanvasTexture {
  if (!PARTICLE_TEX_CACHE[kind]) PARTICLE_TEX_CACHE[kind] = makeParticleTexture(kind);
  return PARTICLE_TEX_CACHE[kind]!;
}

function ParticleOverlay({
  expression,
  headY,
  headSpread,
}: {
  expression: Expression;
  /** World-space Y coordinate near the character's head. */
  headY: number;
  /** World-space X spread (character width) for scattering particles. */
  headSpread: number;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const spritesRef = useRef<THREE.Sprite[]>([]);
  const kind = MOOD_PROFILES[expression].particles;

  useEffect(() => {
    const group = groupRef.current;
    if (!group) return;
    for (const sprite of spritesRef.current) {
      group.remove(sprite);
      sprite.material.dispose();
    }
    spritesRef.current = [];
    if (kind === "none") return;

    const tex = particleTextureFor(kind);
    const COUNT = kind === "sparkles" ? 6 : 4;
    for (let i = 0; i < COUNT; i++) {
      const mat = new THREE.SpriteMaterial({
        map: tex,
        transparent: true,
        depthWrite: false,
        depthTest: false, // Draw on top of the mesh so it reads clearly.
      });
      const sprite = new THREE.Sprite(mat);
      // World-unit sprite sizes - these are visible against a 1.5m
      // tall character.
      const scale = kind === "sparkles" ? 0.22 : 0.3;
      sprite.scale.set(scale, scale, scale);
      sprite.userData.seed = Math.random();
      sprite.renderOrder = 10;
      group.add(sprite);
      spritesRef.current.push(sprite);
    }
  }, [kind]);

  useFrame((state) => {
    if (kind === "none") return;
    const t = state.clock.getElapsedTime();
    for (let i = 0; i < spritesRef.current.length; i++) {
      const sprite = spritesRef.current[i];
      const seed = sprite.userData.seed as number;
      const phase = (t * 0.6 + seed) % 1;
      const count = spritesRef.current.length;
      const xBase = (i - (count - 1) / 2) * (headSpread / Math.max(1, count - 1));
      if (kind === "tears") {
        sprite.position.set(
          xBase * 0.4,
          headY * 0.9 - phase * headY * 0.5,
          0.25,
        );
        sprite.material.opacity = Math.max(0, 1 - phase * 1.4);
      } else if (kind === "sparkles") {
        const angle = phase * Math.PI * 2;
        sprite.position.set(
          xBase * 0.9 + Math.cos(angle) * headSpread * 0.3,
          headY + Math.sin(angle) * headY * 0.15,
          0.2,
        );
        sprite.material.opacity = 0.7 + 0.3 * Math.sin(t * 3 + seed * Math.PI * 2);
      } else {
        // shimmer - drifts upward above the crown
        sprite.position.set(
          xBase * 0.5,
          headY + 0.1 + phase * 0.5,
          0.15,
        );
        sprite.material.opacity = Math.max(0, 1 - phase);
      }
    }
  });

  return <group ref={groupRef} />;
}

/* ---------------------------------------------------------------------
 * Character — loads the GLB, plays the active clip, applies mood tint.
 * ------------------------------------------------------------------- */

function Character({
  expression,
  activeClip,
  holdStone = false,
}: {
  expression: Expression;
  activeClip: ClipName;
  holdStone?: boolean;
}) {
  // Outer group: owns the mood posture (tilt + lean). Scale stays at 1.
  const outerRef = useRef<THREE.Group>(null);
  // Inner group: owns the character's uniform scale + ground offset +
  // mood pulse. Kept separate so the ParticleOverlay (sibling, not
  // child) can stay in world units and render at sensible sprite sizes.
  const innerRef = useRef<THREE.Group>(null);

  const { scene, animations } = useGLTF(MODEL_URL, DRACO_DECODER, false);

  // SkeletonUtils.clone deep-clones the scene AND rebinds every
  // SkinnedMesh's `.skeleton` to the cloned bone chain. Without this,
  // animations would update the cloned bones but the SkinnedMesh would
  // still render using the original (static) ones - which is exactly
  // the "no movement" bug this fixes.
  const cloned = useMemo(() => {
    const next = cloneWithSkeleton(scene) as THREE.Object3D;
    clarifyStoneMesh(next);
    return next;
  }, [scene]);

  // drei's useAnimations wires an AnimationMixer to the inner group
  // (which contains the cloned skeleton) and exposes AnimationActions
  // keyed by clip name. The mixer resolves bones by name via
  // PropertyBinding so attaching to the group containing the cloned
  // skeleton is correct.
  const { actions, names } = useAnimations(animations, innerRef);

  // Fit the character to a sensible on-screen size: compute bbox once
  // post-load, pick a scale that makes it ~1.5 m tall, and offset so
  // the feet sit on y = 0 in world coords.
  const { worldHeight, worldWidth, uniformScale, groundOffset } = useMemo(() => {
    const TARGET_HEIGHT = 1.5;
    const box = new THREE.Box3().setFromObject(cloned);
    const size = new THREE.Vector3();
    box.getSize(size);
    const h = Math.max(0.001, size.y);
    const scale = TARGET_HEIGHT / h;
    return {
      worldHeight: TARGET_HEIGHT,
      worldWidth: size.x * scale,
      uniformScale: scale,
      groundOffset: -box.min.y * scale,
    };
  }, [cloned]);

  // Snapshot original emissive values once so mood tints reset cleanly
  // between expressions instead of stacking.
  const emissiveSnaps = useMemo(() => snapshotEmissives(cloned), [cloned]);

  // Debug: log the clip + material inventory once per mount so DevTools
  // confirms the GLB loaded with the expected skeleton + animations.
  // (Facial shape-key morphing was tried in v0.71.0 and reverted at
  // the user's request - the stone face does not deform naturally;
  // mood is now expressed only via color tint + posture + particles.)
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.info(
      `[MascotMeshy] loaded ${names.length} clips, tinting ${emissiveSnaps.length} materials, scale=${uniformScale.toFixed(4)}`,
      { names },
    );
  }, [names, emissiveSnaps.length, uniformScale]);

  // Apply mood tint whenever expression changes. Setup assistant pages
  // hold the voice-check bronze (the cute grade, no extra wash).
  useEffect(() => {
    applyMoodTint(emissiveSnaps, holdStone ? MOOD_PROFILES.cute : MOOD_PROFILES[expression]);
  }, [emissiveSnaps, expression, holdStone]);

  // Play the active clip. Fade between clip changes.
  useEffect(() => {
    if (!actions) return;
    const match = names.find((n) => n.toLowerCase() === activeClip.toLowerCase());
    if (!match) {
      // eslint-disable-next-line no-console
      console.warn(`[MascotMeshy] clip "${activeClip}" not in Mascot.glb; have:`, names);
      return;
    }
    const action = actions[match];
    if (!action) return;
    action.reset().setLoop(THREE.LoopRepeat, Infinity).fadeIn(0.35).play();
    return () => {
      action.fadeOut(0.35);
    };
  }, [actions, names, activeClip]);

  // Posture + pulse layer on top of the clip's own skeletal motion.
  useFrame((state) => {
    const outer = outerRef.current;
    const inner = innerRef.current;
    if (!outer || !inner) return;
    const mood = MOOD_PROFILES[expression];
    const t = state.clock.getElapsedTime();
    const pulse = mood.pulseHz > 0
      ? 1 + Math.sin(t * mood.pulseHz * Math.PI * 2) * mood.pulseAmp
      : 1;
    // Posture on the outer group (world units).
    outer.rotation.z = mood.bodyTiltZ;
    outer.rotation.x = mood.bodyLeanX;
    // Scale + ground offset on the inner group so particles (sibling)
    // can live in world units with sensible sprite sizes.
    inner.scale.setScalar(uniformScale * pulse);
    inner.position.y = groundOffset;
  });

  return (
    <group ref={outerRef}>
      <group ref={innerRef}>
        <primitive object={cloned} />
      </group>
      {/* Particles are OUTSIDE innerRef so sprite positions and scales
          live in world units (not multiplied by uniformScale ~ 0.008). */}
      <ParticleOverlay
        expression={expression}
        headY={worldHeight * 0.9}
        headSpread={worldWidth * 0.5}
      />
    </group>
  );
}

/**
 * Camera smoothly pulls out on run and in on idle. Independent of the
 * clip so it works for any motion state the parent picks.
 */
function CameraRig({ motion }: { motion?: MotionState }) {
  const { camera } = useThree();
  useEffect(() => {
    const target = motion === "run" ? [0, 1.15, 3.55]
      : motion === "walk" ? [0, 1.08, 3.2]
      : [0, 1.05, 2.85];
    const start = camera.position.clone();
    const end = new THREE.Vector3(target[0], target[1], target[2]);
    let frame = 0;
    const FRAMES = 20;
    const tick = () => {
      frame += 1;
      const a = Math.min(1, frame / FRAMES);
      camera.position.lerpVectors(start, end, a);
      camera.lookAt(0, 0.82, 0);
      if (frame < FRAMES) requestAnimationFrame(tick);
    };
    tick();
  }, [camera, motion]);
  return null;
}

/**
 * Resolve which clip to play right now from the three driving props.
 * Also owns the idle-rotation timer so the hook is colocated with the
 * component that reads its output.
 */
function useActiveClip(
  motion: MotionState | undefined,
  explicitClip: ClipName | undefined,
  idleRotation: boolean,
  rotationIntervalMs: number,
): ClipName {
  const [rotationIndex, setRotationIndex] = useState(0);
  useEffect(() => {
    if (!idleRotation || motion !== "idle" || explicitClip) return;
    const timer = window.setInterval(() => {
      setRotationIndex((i) => (i + 1) % IDLE_ROTATION.length);
    }, rotationIntervalMs);
    return () => window.clearInterval(timer);
  }, [idleRotation, motion, explicitClip, rotationIntervalMs]);

  if (explicitClip) return explicitClip;
  if (idleRotation && motion === "idle") return IDLE_ROTATION[rotationIndex];
  return MOTION_TO_CLIP[motion ?? "idle"];
}

export default function MascotMeshy({
  expression,
  motion = "idle",
  clip,
  idleRotation = false,
  rotationIntervalMs = 5000,
  size = 480,
  fill = false,
  className,
  interactive = false,
  transparent = false,
  backdrop,
  paused = false,
  holdStone = false,
}: Props) {
  const activeClip = useActiveClip(motion, clip, idleRotation, rotationIntervalMs);
  const [canvasKey, setCanvasKey] = useState(0);
  const restores = useRef(0);
  const pausedRef = useRef(paused);
  const glRef = useRef<THREE.WebGLRenderer | null>(null);
  pausedRef.current = paused;
  useEffect(() => {
    if (paused) return;
    const gl = glRef.current;
    if (!gl || !gl.getContext().isContextLost() || restores.current >= 2) return;
    restores.current += 1;
    setCanvasKey((key) => key + 1);
  }, [paused]);
  const wrapperStyle: React.CSSProperties = fill
    ? { position: "absolute", inset: 0 }
    : { position: "relative", width: size, height: size, display: "block" };

  return (
    <div className={className} style={wrapperStyle}>
      <Canvas
        key={canvasKey}
        shadows
        camera={{ position: [0, 1.05, 2.85], fov: 30 }}
        dpr={[1, 2]}
        frameloop={paused ? "never" : "always"}
        gl={{
          alpha: !backdrop && transparent,
          antialias: true,
          premultipliedAlpha: Boolean(backdrop) || !transparent,
        }}
        style={{
          position: "absolute",
          inset: 0,
          background: backdrop ?? (transparent ? "transparent" : "#111318"),
          // Fiber's canvas root defaults to pointer-events:auto, which
          // re-enables hits even when a parent set pointer-events:none.
          // That full-size canvas was swallowing the consent button.
          pointerEvents: interactive ? "auto" : "none",
        }}
        onCreated={({ gl }) => {
          glRef.current = gl;
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 0.92;
          if (backdrop) gl.setClearColor(backdrop, 1);
          else if (transparent) gl.setClearColor(0x000000, 0);
          const onLost = (event: Event) => {
            event.preventDefault();
            // The face check hides this canvas. Rebuilding it then fights the
            // camera and logs a second context loss. Leave it until it is shown.
            if (pausedRef.current || !gl.domElement.isConnected || restores.current >= 2) return;
            restores.current += 1;
            window.setTimeout(() => setCanvasKey((key) => key + 1), 40);
          };
          gl.domElement.addEventListener("webglcontextlost", onLost);
        }}
      >
        <ambientLight intensity={0.46} />
        <hemisphereLight args={["#f3e6cf", "#3a2e22", 0.38]} />
        <directionalLight
          position={[1.4, 3.6, 2.2]}
          intensity={1.05}
          color="#fff1d6"
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <directionalLight position={[-2.4, 1.1, 1.6]} intensity={0.22} color="#f0e2c4" />
        <directionalLight position={[-0.4, 1.8, -2.6]} intensity={0.18} color="#f4e7cf" />

        <Suspense fallback={null}>
          <Character expression={expression} activeClip={activeClip} holdStone={holdStone} />
        </Suspense>

        <ContactShadows
          position={[0, 0, 0]}
          opacity={0.55}
          scale={5}
          blur={2.4}
          far={2}
        />
        {backdrop || transparent ? null : <Environment preset="apartment" />}
        <CameraRig motion={motion} />
        {interactive && <OrbitControls enablePan={false} enableZoom={true} target={[0, 0.82, 0]} />}
      </Canvas>
    </div>
  );
}

useGLTF.preload(MODEL_URL, DRACO_DECODER, false);

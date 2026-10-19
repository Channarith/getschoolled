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
}: {
  expression: Expression;
  activeClip: ClipName;
}) {
  // Outer group: owns the mood posture (tilt + lean). Scale stays at 1.
  const outerRef = useRef<THREE.Group>(null);
  // Inner group: owns the character's uniform scale + ground offset +
  // mood pulse. Kept separate so the ParticleOverlay (sibling, not
  // child) can stay in world units and render at sensible sprite sizes.
  const innerRef = useRef<THREE.Group>(null);

  const { scene, animations } = useGLTF(MODEL_URL);

  // SkeletonUtils.clone deep-clones the scene AND rebinds every
  // SkinnedMesh's `.skeleton` to the cloned bone chain. Without this,
  // animations would update the cloned bones but the SkinnedMesh would
  // still render using the original (static) ones - which is exactly
  // the "no movement" bug this fixes.
  const cloned = useMemo(() => cloneWithSkeleton(scene) as THREE.Object3D, [scene]);

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

  // Debug: log the clip inventory + material count once per mount so
  // the browser console confirms the GLB loaded with the expected
  // skeleton + animations.
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.info(
      `[MascotMeshy] loaded ${names.length} clips, tinting ${emissiveSnaps.length} materials, scale=${uniformScale.toFixed(4)}`,
      { names },
    );
  }, [names, emissiveSnaps.length, uniformScale]);

  // Apply mood tint whenever expression changes.
  useEffect(() => {
    applyMoodTint(emissiveSnaps, MOOD_PROFILES[expression]);
  }, [emissiveSnaps, expression]);

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
    const target = motion === "run" ? [0, 1.3, 4.2]
      : motion === "walk" ? [0, 1.2, 3.8]
      : [0, 1.1, 3.4];
    const start = camera.position.clone();
    const end = new THREE.Vector3(target[0], target[1], target[2]);
    let frame = 0;
    const FRAMES = 20;
    const tick = () => {
      frame += 1;
      const a = Math.min(1, frame / FRAMES);
      camera.position.lerpVectors(start, end, a);
      camera.lookAt(0, 0.7, 0);
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
}: Props) {
  const activeClip = useActiveClip(motion, clip, idleRotation, rotationIntervalMs);
  const wrapperStyle: React.CSSProperties = fill
    ? { width: "100%", height: "100%", display: "block" }
    : { width: size, height: size, display: "block" };

  return (
    <div className={className} style={wrapperStyle}>
      <Canvas
        shadows
        camera={{ position: [0, 1.1, 3.4], fov: 32 }}
        dpr={[1, 2]}
      >
        <ambientLight intensity={0.55} />
        <directionalLight
          position={[2.5, 4, 3]}
          intensity={1.1}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <directionalLight position={[-3, 2, -2]} intensity={0.3} color="#88aaff" />

        <Suspense fallback={null}>
          <Character expression={expression} activeClip={activeClip} />
        </Suspense>

        <ContactShadows
          position={[0, 0, 0]}
          opacity={0.55}
          scale={5}
          blur={2.4}
          far={2}
        />
        <Environment preset="apartment" />
        <CameraRig motion={motion} />
        {interactive && <OrbitControls enablePan={false} enableZoom={true} target={[0, 0.7, 0]} />}
      </Canvas>
    </div>
  );
}

useGLTF.preload(MODEL_URL);

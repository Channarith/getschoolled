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

type OriginalEmissive = {
  mat: THREE.MeshStandardMaterial;
  color: THREE.Color;
  intensity: number;
};
function snapshotEmissives(root: THREE.Object3D): OriginalEmissive[] {
  const snaps: OriginalEmissive[] = [];
  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    for (const m of mats) {
      if (m instanceof THREE.MeshStandardMaterial) {
        snaps.push({
          mat: m,
          color: m.emissive.clone(),
          intensity: m.emissiveIntensity,
        });
      }
    }
  });
  return snaps;
}

function applyMoodTint(snaps: OriginalEmissive[], mood: MoodProfile): void {
  for (const s of snaps) {
    s.mat.emissive.copy(s.color).add(
      new THREE.Color(mood.emissive[0], mood.emissive[1], mood.emissive[2]),
    );
    s.mat.emissiveIntensity = s.intensity + mood.emissiveIntensity;
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
  bboxTop,
  bboxWidth,
}: {
  expression: Expression;
  bboxTop: number;
  bboxWidth: number;
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
    const COUNT = kind === "sparkles" ? 5 : 3;
    for (let i = 0; i < COUNT; i++) {
      const mat = new THREE.SpriteMaterial({
        map: tex,
        transparent: true,
        depthWrite: false,
        depthTest: true,
      });
      const sprite = new THREE.Sprite(mat);
      const scale = kind === "sparkles" ? 0.14 : 0.22;
      sprite.scale.set(scale, scale, scale);
      sprite.userData.seed = Math.random();
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
      const spread = bboxWidth * 0.55;
      const xBase = (i - (spritesRef.current.length - 1) / 2) * (spread / Math.max(1, spritesRef.current.length - 1));
      if (kind === "tears") {
        sprite.position.set(
          xBase * 0.45,
          bboxTop * 0.92 - phase * bboxTop * 0.4,
          0.12,
        );
        sprite.material.opacity = Math.max(0, 1 - phase * 1.4);
      } else if (kind === "sparkles") {
        const angle = phase * Math.PI * 2;
        sprite.position.set(
          xBase * 0.6 + Math.cos(angle) * bboxWidth * 0.08,
          bboxTop + Math.sin(angle) * bboxTop * 0.08,
          0.08,
        );
        sprite.material.opacity = 0.65 + 0.35 * Math.sin(t * 3 + seed * Math.PI * 2);
      } else {
        sprite.position.set(
          xBase * 0.3,
          bboxTop * 1.05 + phase * bboxTop * 0.25,
          0.05,
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
  const groupRef = useRef<THREE.Group>(null);
  const { scene, animations } = useGLTF(MODEL_URL);

  // Clone the scene so React double-mount is safe. We clone the whole
  // graph (including skinned mesh + skeleton) so the two instances
  // never share bone matrices.
  const cloned = useMemo(() => {
    // SkeletonUtils.clone would be ideal here but is tree-shaken out of
    // bundler builds that don't import it. For a single mount at a
    // time (strict mode is the only reason to clone), a deep clone is
    // sufficient.
    return scene.clone(true);
  }, [scene]);

  // drei's useAnimations wires an AnimationMixer to the ref'd group and
  // exposes a dictionary of AnimationActions keyed by clip name.
  const { actions, names } = useAnimations(animations, groupRef);

  // Fit the character to a sensible on-screen size: find bbox after
  // loading, scale uniformly so the character is ~1.5 m tall, and
  // offset so the feet sit on y = 0.
  const { bboxTop, bboxWidth, uniformScale, groundOffset } = useMemo(() => {
    const TARGET_HEIGHT = 1.5;
    const box = new THREE.Box3().setFromObject(cloned);
    const size = new THREE.Vector3();
    box.getSize(size);
    const height = Math.max(0.001, size.y);
    const scale = TARGET_HEIGHT / height;
    return {
      bboxTop: TARGET_HEIGHT * 0.92,
      bboxWidth: size.x * scale,
      uniformScale: scale,
      groundOffset: -box.min.y * scale,
    };
  }, [cloned]);

  // Snapshot every material's original emissive once so mood tints
  // reset cleanly between expressions instead of stacking.
  const emissiveSnaps = useMemo(() => snapshotEmissives(cloned), [cloned]);

  useEffect(() => {
    applyMoodTint(emissiveSnaps, MOOD_PROFILES[expression]);
  }, [emissiveSnaps, expression]);

  // Play the active clip. Fade between clip changes.
  useEffect(() => {
    if (!actions) return;
    // Find the clip (case-insensitive to survive casing drift).
    const match = names.find((n) => n.toLowerCase() === activeClip.toLowerCase());
    if (!match) {
      // Clip missing from the glTF - log once so the next prep run
      // adds it, don't throw.
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

  // Mood pulse (scale breath) layers on top of the clip's own motion.
  useFrame((state) => {
    const g = groupRef.current;
    if (!g) return;
    const mood = MOOD_PROFILES[expression];
    const t = state.clock.getElapsedTime();
    const pulse = mood.pulseHz > 0
      ? 1 + Math.sin(t * mood.pulseHz * Math.PI * 2) * mood.pulseAmp
      : 1;
    g.scale.setScalar(uniformScale * pulse);
    g.rotation.z = mood.bodyTiltZ;
    g.rotation.x = mood.bodyLeanX;
    g.position.y = groundOffset;
  });

  return (
    <group ref={groupRef}>
      <primitive object={cloned} />
      <ParticleOverlay expression={expression} bboxTop={bboxTop} bboxWidth={bboxWidth} />
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

"use client";

/**
 * MascotMeshy — real Meshy.ai-generated Bayon Buddy mascot renderer
 * with mood overlays and motion.
 *
 * Loads apps/web/public/mascot3d/Mascot.glb (static, no skeleton,
 * produced by the user's Meshy.ai image-to-3D run and slimmed via
 * scripts/mascot_meshy_prep.py from 93.7 MB -> 4.4 MB), then drives:
 *
 *   - Motion (idle / walk / run) via whole-body transforms: a vertical
 *     hop + forward lean + yaw sway. The mesh has no rig so we can't
 *     bend a knee; a hop reads unambiguously as walk/run at the eye
 *     level we show the character.
 *
 *   - Expression (cute / serious / angry / sad / crying / excited /
 *     curious / mischievous) via mood overlays authored in
 *     ./mascot3d/expressions.ts - a per-material emissive tint, a
 *     resting body tilt + lean, an optional scale pulse, and an
 *     optional particle sprite overlay (tears / sparkles / heat
 *     shimmer). This preserves the sculpted-stone aesthetic that a
 *     cartoon Canvas2D face plane would ruin, while still giving
 *     each expression a clearly distinct read.
 *
 * To upgrade from mood overlays to proper facial deformation + rigged
 * limb animation, pass the slim mesh through Mixamo for auto-rig and
 * through scripts/mascot_blender_postprocess.py to merge Idle /
 * Walking / Running clips - after which this renderer can be replaced
 * with the glTF-animation path in MascotActor3D.tsx.
 */

import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  OrbitControls,
  useGLTF,
} from "@react-three/drei";
import * as THREE from "three";

import {
  type Expression,
  MOOD_PROFILES,
  type MoodProfile,
} from "./mascot3d/expressions";

const MODEL_URL = "/mascot3d/Mascot.glb";

export type MotionState = "idle" | "walk" | "run";

type Props = {
  /** Current facial / mood expression. Hot-swappable. */
  expression: Expression;
  /** Idle / walk / run. */
  motion: MotionState;
  /** Pixel size of the canvas (square). Default 480. */
  size?: number;
  className?: string;
  /** True = show mouse-drag orbit controls (handy in the lab, off in prod). */
  interactive?: boolean;
};

/**
 * Walks the loaded glTF and snapshots every MeshStandardMaterial's
 * original emissive color + intensity so we can restore them when the
 * expression changes to one with no emissive (otherwise the mood tint
 * stacks forever).
 */
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

/**
 * Mood-driven particle overlay. Rendered as three billboarded sprites
 * near the character's head region so even an orbiting camera still
 * sees the particles face-on. The sprite textures are drawn procedurally
 * from Canvas2D so there is no PNG asset to ship.
 */
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
    // Teardrop: round bulb + triangular pointed top, pale cyan.
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
    // Highlight glint.
    ctx.fillStyle = "rgba(255,255,255,0.75)";
    ctx.beginPath();
    ctx.arc(SIZE / 2 - SIZE * 0.08, SIZE * 0.6, SIZE * 0.06, 0, Math.PI * 2);
    ctx.fill();
  } else if (kind === "sparkles") {
    // Four-point star in warm gold.
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
    // Soft bloom halo.
    const grd = ctx.createRadialGradient(SIZE / 2, SIZE / 2, 0, SIZE / 2, SIZE / 2, SIZE / 2);
    grd.addColorStop(0, "rgba(255,240,180,0.5)");
    grd.addColorStop(1, "rgba(255,240,180,0)");
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, SIZE, SIZE);
  } else {
    // Heat shimmer: wavy orange gradient blob.
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

/**
 * Three independent particle sprites that drift / float / fall. Reads
 * the mood profile each frame via `expression` prop so swapping
 * expressions updates the overlay without rebuilding the mesh.
 */
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
    // Remove any previous sprites.
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
      // X offset: fan the particles around the head region.
      const spread = bboxWidth * 0.55;
      const xBase = (i - (spritesRef.current.length - 1) / 2) * (spread / Math.max(1, spritesRef.current.length - 1));
      if (kind === "tears") {
        // Fall from eye-level to below the chin.
        sprite.position.set(
          xBase * 0.45,
          bboxTop * 0.92 - phase * bboxTop * 0.4,
          0.12,
        );
        sprite.material.opacity = Math.max(0, 1 - phase * 1.4);
      } else if (kind === "sparkles") {
        // Orbit around the head area.
        const angle = phase * Math.PI * 2;
        sprite.position.set(
          xBase * 0.6 + Math.cos(angle) * bboxWidth * 0.08,
          bboxTop + Math.sin(angle) * bboxTop * 0.08,
          0.08,
        );
        sprite.material.opacity = 0.65 + 0.35 * Math.sin(t * 3 + seed * Math.PI * 2);
      } else {
        // Shimmer: slow upward drift above the head, fading.
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

/**
 * The animated glTF character + mood overlay + motion. One component
 * so the particle overlay can read the mesh's bounding box.
 */
function Character({
  expression,
  motion,
}: {
  expression: Expression;
  motion: MotionState;
}) {
  const bodyRef = useRef<THREE.Group>(null);
  const { scene } = useGLTF(MODEL_URL);

  // Clone the scene so React strict-mode double-mount is safe and
  // so a future second instance (overlay vs lab) does not fight for
  // the same materials.
  const cloned = useMemo(() => scene.clone(true), [scene]);

  // Compute a bounding box once per load so we know where the "head
  // region" is (upper quarter) for the particle overlay and so we can
  // auto-centre the model at the ground plane y = 0.
  const { bboxSize, bboxCentre, bboxTop } = useMemo(() => {
    const box = new THREE.Box3().setFromObject(cloned);
    const size = new THREE.Vector3();
    const centre = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(centre);
    // Shift so the feet land on y = 0.
    cloned.position.set(-centre.x, -box.min.y, -centre.z);
    return { bboxSize: size, bboxCentre: centre, bboxTop: size.y };
  }, [cloned]);

  // Snapshot every material's original emissive once so mood tints
  // reset cleanly between expressions instead of stacking.
  const emissiveSnaps = useMemo(() => snapshotEmissives(cloned), [cloned]);

  // Re-apply the mood tint whenever expression changes.
  useEffect(() => {
    applyMoodTint(emissiveSnaps, MOOD_PROFILES[expression]);
  }, [emissiveSnaps, expression]);

  // Drive position / rotation / scale each frame from the current
  // motion state + mood posture.
  useFrame((state) => {
    const body = bodyRef.current;
    if (!body) return;
    const t = state.clock.getElapsedTime();
    const mood = MOOD_PROFILES[expression];

    // Resting body pose from the mood profile.
    const baseTiltZ = mood.bodyTiltZ;
    const baseLeanX = mood.bodyLeanX;

    // Motion-driven transforms.
    if (motion === "walk" || motion === "run") {
      const freq = motion === "run" ? 3.0 : 1.6;
      const hop = motion === "run" ? 0.14 : 0.07;
      const lean = motion === "run" ? 0.15 : 0.08;
      const phase = t * freq * Math.PI * 2;
      // Hop uses |sin| so each footfall is a bounce.
      const hopY = Math.abs(Math.sin(phase)) * hop;
      body.position.y = hopY;
      // Forward lean peaks during the airborne middle of a hop.
      body.rotation.x = baseLeanX + Math.sin(phase) * lean * 0.3;
      // Slight yaw sway (character scans side-to-side as it moves).
      body.rotation.y = Math.sin(t * freq * 0.5) * 0.1;
      body.rotation.z = baseTiltZ + Math.sin(phase * 0.5) * 0.03;
    } else {
      // Idle: slow breath + slow yaw sway + mood posture.
      const breath = Math.sin(t * 1.0) * 0.012;
      body.position.y = breath;
      body.rotation.x = baseLeanX;
      body.rotation.y = Math.sin(t * 0.35) * 0.18;
      body.rotation.z = baseTiltZ;
    }

    // Mood pulse: slight scale breathing for excited / angry etc.
    if (mood.pulseHz > 0) {
      const pulse = 1 + Math.sin(t * mood.pulseHz * Math.PI * 2) * mood.pulseAmp;
      body.scale.setScalar(pulse);
    } else {
      body.scale.setScalar(1);
    }
  });

  return (
    <group ref={bodyRef}>
      <primitive object={cloned} />
      {/* Particle overlay sits at head-top in local-space so it moves
          + tilts with the body transforms above. */}
      <ParticleOverlay
        expression={expression}
        bboxTop={bboxTop}
        bboxWidth={bboxSize.x}
      />
    </group>
  );
}

/**
 * On motion state changes, re-position the camera so running pulls
 * out a little and idle sits closer. Purely cosmetic, feels right.
 */
function CameraRig({ motion }: { motion: MotionState }) {
  const { camera } = useThree();
  useEffect(() => {
    const targetZ = motion === "run" ? 4.2 : motion === "walk" ? 3.8 : 3.4;
    const targetY = motion === "idle" ? 1.1 : 1.25;
    const start = camera.position.clone();
    const end = new THREE.Vector3(0, targetY, targetZ);
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

export default function MascotMeshy({
  expression,
  motion,
  size = 480,
  className,
  interactive = false,
}: Props) {
  return (
    <div
      className={className}
      style={{ width: size, height: size, display: "block" }}
    >
      <Canvas
        shadows
        camera={{ position: [0, 1.1, 3.4], fov: 32 }}
        dpr={[1, 2]}
      >
        {/* Warm key + cool rim light. */}
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
          <Character expression={expression} motion={motion} />
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
        {interactive && <OrbitControls enablePan={false} enableZoom={true} />}
      </Canvas>
    </div>
  );
}

// Preload so the first paint on /mascot-lab is instant.
useGLTF.preload(MODEL_URL);

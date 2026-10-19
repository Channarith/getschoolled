"use client";

/**
 * MascotOverlay3D — a video-game-style interactive mascot that lives in a
 * fixed full-viewport canvas OVERLAID on the whole app. Unlike MascotActor3D
 * (which renders inside a small art pane), this character:
 *
 *   - fills the entire browser viewport
 *   - walks across the screen with a real glTF skeletal animation
 *   - rotates to face its target
 *   - visits UI elements tagged with `data-mascot-target="<name>"` in order
 *   - plays Survey (idle) at each target for a dwell time, then moves on
 *   - draws a soft "look here" pulse overlay at the current target so the
 *     user sees exactly what the mascot is pointing to
 *   - uses `pointer-events: none` so it never blocks real clicks
 *
 * Target coordination:
 *   1. Each UI element you want the mascot to visit gets a
 *      `data-mascot-target="<name>"` attribute.
 *   2. STEP_TOURS below maps each onboarding step to an ordered list of
 *      target names. The mascot walks the list on loop.
 *   3. The character uses raycasting through the camera to turn screen
 *      coordinates into world coordinates on the ground plane (Y = 0).
 *
 * Swap-in a custom character the same way as MascotActor3D:
 *   drop a rigged .glb at /mascot3d/Mascot.glb (clip names Survey/Walk/Run)
 *   and change MODEL_URL below.
 */

import {
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Canvas,
  useFrame,
  useThree,
} from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  useAnimations,
  useGLTF,
} from "@react-three/drei";
import * as THREE from "three";

import type { MascotScene } from "../lib/mascotPose";
// buddhaFoxStyle was the Fox.glb reskin helper - retired with the
// placeholder. Mascot.glb ships with its own baked PBR materials.

// The real Meshy character (3.12 MB, 1 skin, 15 Mixamo clips including
// Walking / Running / Big_Wave_Hello / Indoor_Swing / Boom_Dance /
// _360_Power_Spin_Jump / Wave_for_Help_1 / Confident_Strut / ...). Lands
// at the public asset path produced by scripts/mascot_meshy_prep.py.
const MODEL_URL = "/mascot3d/Mascot.glb";

/**
 * Ordered waypoints per onboarding step. Each name must appear somewhere
 * in the DOM as a `data-mascot-target="<name>"` attribute. If a name is
 * missing (because that step hasn't rendered the element yet), the mascot
 * simply skips it and tries the next one.
 */
const STEP_TOURS: Record<string, string[]> = {
  account: ["account-email", "account-password", "account-submit"],
  about: ["about-name", "about-age", "about-continue"],
  learn: ["learn-card", "learn-continue"],
  // "identity" (Learner Check) intentionally has no tour and is hidden
  // upstream in MascotActorChoice (MASCOT_HIDDEN_STEPS). The stylized
  // Buddha-fox character read as a cultural caricature while learners
  // were looking at their own face on camera, so the whole mascot layer
  // is suppressed on that one step.
  plan: ["plan-free", "plan-pro", "plan-continue"],
  payment: ["pay-card", "pay-submit"],
};

type Props = {
  /** Which onboarding step we are on; drives the tour. */
  step?: string;
  /** The scene (idle/dance/etc) chooses an animation when at rest. */
  scene?: MascotScene;
  /** Dwell time at each waypoint in seconds. */
  dwell?: number;
  /** Walking speed in world-units/sec (world unit ≈ 1 metre). */
  speed?: number;
};

const DEFAULT_DWELL = 2.4;
const DEFAULT_SPEED = 2.6;
const ARRIVAL_RADIUS = 0.35; // world units

/**
 * Resolve the current waypoint's center position in screen pixels.
 * Returns null when the DOM element is missing or offscreen.
 */
function screenCenterOf(name: string): { x: number; y: number } | null {
  if (typeof document === "undefined") return null;
  const el = document.querySelector<HTMLElement>(`[data-mascot-target="${name}"]`);
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return null;
  // Point slightly BELOW the element so the character stands at its base
  // instead of overlapping. Fine-tuned on 1024px wide onboarding.
  return { x: rect.left + rect.width / 2, y: rect.bottom + 32 };
}

/**
 * Map a screen-pixel point to a world-space point on the ground plane
 * (Y = 0) by raycasting through the camera.
 */
function screenToGround(
  xPx: number,
  yPx: number,
  camera: THREE.Camera,
  size: { width: number; height: number },
): THREE.Vector3 | null {
  const ndc = new THREE.Vector2(
    (xPx / size.width) * 2 - 1,
    -(yPx / size.height) * 2 + 1,
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(ndc, camera);
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hit = new THREE.Vector3();
  const ok = raycaster.ray.intersectPlane(plane, hit);
  return ok ? hit : null;
}

/**
 * The animated character. Driven by:
 *   - targetWorld: where we want to go on the ground plane
 *   - speed: metres/sec
 *   - idleClip: which clip to play when we're at the target
 *
 * The character's bones animate via useAnimations; we just move the whole
 * group through 3D space and keep it facing its walk direction.
 */
function Character({
  targetWorldRef,
  arrivedRef,
  speed,
  idleClip,
}: {
  targetWorldRef: React.MutableRefObject<THREE.Vector3 | null>;
  arrivedRef: React.MutableRefObject<boolean>;
  speed: number;
  idleClip: string;
}) {
  const group = useRef<THREE.Group>(null);
  const { scene: gltfScene, animations } = useGLTF(MODEL_URL);
  const { actions, names } = useAnimations(animations, group);

  // Mascot.glb ships with its own baked PBR materials from Meshy - no
  // reskin needed (the old applyBuddhaFoxStyle call was retexturing the
  // Fox placeholder, which is retired). The GLB is self-contained.

  // Resolve clip names fuzzy. Mascot.glb exposes 15 clips - we fuzzy
  // match "walk" (Walking), "run" (Running), and fall back to the first
  // clip (Walking) if idleClip isn't present. Prefer substring/exact
  // match over equality so idleClip="Walking" works even if the stored
  // name is "walking|Walking" after animation re-indexing.
  const walkClip = useMemo(
    () => names.find((n) => /^walking$/i.test(n)) ?? names.find((n) => /walk/i.test(n)) ?? names[0],
    [names],
  );
  const resolvedIdle = useMemo(() => {
    if (!idleClip) return walkClip;
    const exact = names.find((n) => n.toLowerCase() === idleClip.toLowerCase());
    if (exact) return exact;
    const substr = names.find((n) => n.toLowerCase().includes(idleClip.toLowerCase()));
    return substr ?? walkClip;
  }, [names, idleClip, walkClip]);

  // Which action is currently playing. We cross-fade on change.
  const activeRef = useRef<string | null>(null);

  function setActive(next: string | undefined) {
    if (!next || next === activeRef.current) return;
    const current = activeRef.current ? actions[activeRef.current] : null;
    const nextAction = actions[next];
    if (!nextAction) return;
    current?.fadeOut(0.25);
    nextAction.reset().fadeIn(0.25).play();
    activeRef.current = next;
  }

  useEffect(() => {
    // Start idle on mount
    setActive(resolvedIdle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedIdle]);

  useFrame((_state, delta) => {
    const g = group.current;
    if (!g) return;
    const target = targetWorldRef.current;
    if (!target) {
      setActive(resolvedIdle);
      arrivedRef.current = true;
      return;
    }
    const toTarget = new THREE.Vector3().subVectors(target, g.position);
    toTarget.y = 0;
    const dist = toTarget.length();
    if (dist < ARRIVAL_RADIUS) {
      arrivedRef.current = true;
      setActive(resolvedIdle);
      return;
    }
    arrivedRef.current = false;
    setActive(walkClip);
    toTarget.normalize();
    const step = Math.min(dist, speed * delta);
    g.position.add(toTarget.multiplyScalar(step));
    // Face the direction of motion. atan2(x, z) orients +Z-forward meshes.
    const yaw = Math.atan2(toTarget.x, toTarget.z);
    // Smoothly rotate toward yaw.
    const current = g.rotation.y;
    const diff = Math.atan2(Math.sin(yaw - current), Math.cos(yaw - current));
    g.rotation.y = current + diff * Math.min(1, delta * 6);
  });

  // Mascot.glb native dimensions are in meters (~1.8 m tall from the
  // Meshy export + scripts/mascot_meshy_prep.py). With camera at
  // (0, 2.4, 5.5) and fov 42, scale=1.0 reads tiny; scale=1.2 puts the
  // character around 2.1 m which lands comfortably in the lower-left
  // third of the viewport while still clearing the content card.
  return (
    <group ref={group} scale={1.2} position={[0, 0, 0]}>
      <primitive object={gltfScene} />
    </group>
  );
}

/**
 * Bridges the outer DOM (where waypoint elements live) and the Three.js
 * scene. Each render frame it:
 *   - picks the current waypoint from the tour
 *   - converts its DOM position to a world-space target
 *   - advances to the next waypoint after dwell seconds at the current one
 */
function TourDriver({
  tour,
  dwell,
  targetWorldRef,
  arrivedRef,
  setPointerPx,
}: {
  tour: string[];
  dwell: number;
  targetWorldRef: React.MutableRefObject<THREE.Vector3 | null>;
  arrivedRef: React.MutableRefObject<boolean>;
  setPointerPx: (p: { x: number; y: number } | null) => void;
}) {
  const { camera, size } = useThree();
  const indexRef = useRef(0);
  const dwellElapsedRef = useRef(0);

  // Reset to the first waypoint whenever the tour changes.
  useEffect(() => {
    indexRef.current = 0;
    dwellElapsedRef.current = 0;
  }, [tour]);

  useFrame((_state, delta) => {
    if (!tour.length) {
      targetWorldRef.current = null;
      setPointerPx(null);
      return;
    }
    const name = tour[indexRef.current % tour.length];
    const px = screenCenterOf(name);
    if (!px) {
      // Skip missing waypoint — step the index.
      indexRef.current = (indexRef.current + 1) % tour.length;
      return;
    }
    const world = screenToGround(px.x, px.y, camera, { width: size.width, height: size.height });
    if (world) targetWorldRef.current = world;
    setPointerPx(px);

    if (arrivedRef.current) {
      dwellElapsedRef.current += delta;
      if (dwellElapsedRef.current >= dwell) {
        indexRef.current = (indexRef.current + 1) % tour.length;
        dwellElapsedRef.current = 0;
      }
    } else {
      dwellElapsedRef.current = 0;
    }
  });

  return null;
}

export default function MascotOverlay3D({
  step = "about",
  scene,
  dwell = DEFAULT_DWELL,
  speed = DEFAULT_SPEED,
}: Props) {
  const [pointerPx, setPointerPx] = useState<{ x: number; y: number } | null>(null);
  const targetWorldRef = useRef<THREE.Vector3 | null>(null);
  const arrivedRef = useRef(true);

  // Idle clip the character plays while standing AT a waypoint (after
  // walking there and before moving on). Mascot.glb clip names, matched
  // fuzzily by resolvedIdle so a wrong name falls back to Walking:
  //   dance/gaming  -> Boom_Dance (energetic celebrate)
  //   tutoring      -> Wave_for_Help_1 (approachable 1:1 greeting)
  //   flyin-point   -> Big_Wave_Hello (hello / point at me)
  //   teacher       -> Confident_Strut (presenting)
  //   presentation  -> Big_Wave_Hello
  //   video/reading -> Indoor_Swing (calm / watching)
  //   default/idle  -> Indoor_Swing (also the base calm clip)
  const idleClip = useMemo(() => {
    if (!scene) return "Indoor_Swing";
    switch (scene.kind) {
      case "dance":
        return "Boom_Dance";
      case "gaming":
        return "_360_Power_Spin_Jump";
      case "tutoring":
        return "Wave_for_Help_1";
      case "flyin-point":
        return "Big_Wave_Hello";
      case "teacher":
        return "Confident_Strut";
      case "presentation":
        return "Big_Wave_Hello";
      case "video":
      case "reading":
      default:
        return "Indoor_Swing";
    }
  }, [scene]);

  const tour = STEP_TOURS[step] ?? STEP_TOURS.about;

  return (
    <>
      {/* Contrast backdrop: the Meshy character is a cream/gold Buddha
          that disappears into the site's cream (#f4e9d8) page background.
          On 2026-10-19 the user reported the v0.78.0 rgba(26,20,10,0.32)
          wash was still "golden on cream" — the mascot blended in. We
          switched to a bold ocean-blue radial "stage spotlight" centered
          where the character walks (50% x 95%). Gold-on-deep-blue is a
          classic high-contrast pairing and reads clearly without hiding
          the onboarding chrome: the gradient fades to transparent by 70%
          radius so the setup-assistant text/panels above remain legible.
          Lower z-index (999) than the Canvas (1000) so the mascot renders
          ON TOP of this plate, and `pointer-events: none` so page clicks
          still pass through to the onboarding form underneath. */}
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: 0,
          height: "55vh",
          pointerEvents: "none",
          zIndex: 999,
          background:
            "radial-gradient(ellipse 55% 65% at 50% 95%, rgba(11, 34, 56, 1) 0%, rgba(11, 34, 56, 0.78) 20%, rgba(11, 34, 56, 0.42) 45%, rgba(11, 34, 56, 0.12) 62%, rgba(11, 34, 56, 0) 72%)",
        }}
      />
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          inset: 0,
          pointerEvents: "none",
          zIndex: 1000,
        }}
      >
        <Canvas
          camera={{ position: [0, 2.4, 5.5], fov: 42 }}
          shadows
          dpr={[1, 2]}
          style={{ background: "transparent" }}
          gl={{ antialias: true, alpha: true, premultipliedAlpha: false }}
        >
          {/* Lighting tuned to make a cream/gold character pop against a
              deep-ocean-blue stage backdrop (see the radial gradient above,
              updated 2026-10-19 at the user's request for bolder contrast).
              Three-point setup:
              - ambientLight 0.75 (was 0.55): a touch brighter base.
              - keyLight (directional, warm) 2.0 (was 1.15) from front-
                right: strong key so the Buddha's bronze reads as gold,
                not beige.
              - rimLight (directional, cool) 1.8 (was 1.4) from behind-
                left: bumped slightly for the new dark-blue backdrop so
                the cool highlight along the silhouette separates the
                character crisply from the deep ocean blue.
              - hemisphere light with cream-sky / dark-ground: fills in
                shadow sides so the character never goes muddy. */}
          <ambientLight intensity={0.75} />
          <directionalLight
            position={[4, 6, 3]}
            intensity={2.0}
            color={0xfff2d4}
            castShadow
            shadow-mapSize={[1024, 1024]}
          />
          <directionalLight
            position={[-5, 4, -3]}
            intensity={1.8}
            color={0x8ab6ff}
          />
          <hemisphereLight
            color={0xffe8c2}
            groundColor={0x2a1a08}
            intensity={0.5}
          />
          <Suspense fallback={null}>
            <Character
              targetWorldRef={targetWorldRef}
              arrivedRef={arrivedRef}
              speed={speed}
              idleClip={idleClip}
            />
            <TourDriver
              tour={tour}
              dwell={dwell}
              targetWorldRef={targetWorldRef}
              arrivedRef={arrivedRef}
              setPointerPx={setPointerPx}
            />
            <ContactShadows
              position={[0, 0.01, 0]}
              opacity={0.75}
              scale={10}
              blur={2.4}
              far={2}
            />
            <Environment preset="apartment" />
          </Suspense>
        </Canvas>
      </div>
      {/* The glowing pulse at the current waypoint. Rendered as HTML (not
          inside the Canvas) so it crisply tracks the DOM element even while
          the character is still walking there. */}
      {pointerPx && (
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            left: pointerPx.x - 32,
            top: pointerPx.y - 32,
            width: 64,
            height: 64,
            pointerEvents: "none",
            zIndex: 1001,
            borderRadius: "50%",
            boxShadow:
              "0 0 0 2px rgba(250, 196, 72, 0.75), 0 0 32px 6px rgba(250, 196, 72, 0.45)",
            animation: "aoep-mascot-pulse 1.6s ease-in-out infinite",
          }}
        />
      )}
      <style>{`
        @keyframes aoep-mascot-pulse {
          0%, 100% { transform: scale(1); opacity: 0.9; }
          50%      { transform: scale(1.12); opacity: 0.55; }
        }
      `}</style>
    </>
  );
}

useGLTF.preload(MODEL_URL);

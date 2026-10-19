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
import { applyBuddhaFoxStyle } from "./mascot3d/buddhaFoxStyle";

const MODEL_URL = "/mascot3d/Fox.glb";

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

  // Reskin the Fox base into the Salareen Buddha-fox: stone-tan body +
  // gold lotus crown + forehead gem + navy/gold S medallion. Idempotent
  // via a userData flag so React strict-mode double-mount doesn't dupe.
  useEffect(() => {
    if (gltfScene) applyBuddhaFoxStyle(gltfScene);
  }, [gltfScene]);

  // Resolve clip names fuzzy — Fox has "Survey" / "Walk" / "Run".
  const walkClip = useMemo(
    () => names.find((n) => /walk/i.test(n)) ?? names[0],
    [names],
  );
  const resolvedIdle = useMemo(
    () => names.find((n) => n.toLowerCase() === idleClip.toLowerCase()) ?? names[0],
    [names, idleClip],
  );

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

  return (
    <group ref={group} scale={0.012} position={[0, 0, 0]}>
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

  // When "dance" or "gaming" scene is set, the character does the Run clip
  // instead of Survey while idling at a waypoint. Everything else falls
  // through to Survey.
  const idleClip = useMemo(() => {
    if (!scene) return "Survey";
    switch (scene.kind) {
      case "dance":
      case "gaming":
        return "Run";
      case "flyin-point":
      case "video":
      case "teacher":
      case "presentation":
      case "tutoring":
        return "Walk";
      default:
        return "Survey";
    }
  }, [scene]);

  const tour = STEP_TOURS[step] ?? STEP_TOURS.about;

  return (
    <>
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
          <ambientLight intensity={0.55} />
          <directionalLight
            position={[4, 6, 3]}
            intensity={1.15}
            castShadow
            shadow-mapSize={[1024, 1024]}
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
              opacity={0.4}
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

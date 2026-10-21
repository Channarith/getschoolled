"use client";

/**
 * MascotOverlay3D — the setup-assistant mesh. The Meshy character
 * (public/mascot3d/Mascot.glb) is a screen overlay: it shares the viewport
 * with the form, walks inside the art stage, and turns toward the active
 * control. A small marker sits on that control. Clicks pass through.
 *
 *   - position:fixed over the viewport, so screen pixels match the form
 *   - feet stay inside [data-mascot-stage] (left stage on desktop, top
 *     band on a phone), lined up with the active field
 *   - scale is derived from that stage so the body fits it
 *   - plays an idle clip at each stop, then walks to the next
 *
 * Target coordination:
 *   1. Tag a control with `data-mascot-target="<name>"`.
 *   2. Tag the stage with `data-mascot-stage`.
 *   3. STEP_TOURS maps each onboarding step to an ordered list of names.
 *   4. Raycasting turns those screen points into ground-plane positions.
 */

import {
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
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
 * Responsive breakpoint tags. Resolved from window.innerWidth +
 * innerHeight so we can also distinguish phone-landscape (which falls
 * back to the tablet treatment per the product spec).
 */
type Breakpoint = "desktop" | "tablet" | "phonePortrait";

/**
 * Per-breakpoint camera. `scale` is a ceiling. The live scale is computed
 * from the art stage height so the ~1.8 m mesh fills that stage and stays
 * beside the form.
 *
 *   - desktop (>=1024px landscape): left stage, about half the window.
 *   - tablet and phone landscape: same side-by-side stage.
 *   - phone portrait (<768px): the stage is a short band above the form.
 */
type BreakpointConfig = {
  cameraPos: [number, number, number];
  cameraLookAt: [number, number, number];
  fov: number;
  scale: number;
};

const BREAKPOINT_CONFIG: Record<Breakpoint, BreakpointConfig> = {
  desktop: {
    cameraPos: [0, 1.9, 5.6],
    cameraLookAt: [0, 1.05, 0],
    fov: 42,
    scale: 1.5,
  },
  tablet: {
    cameraPos: [0, 1.85, 5.8],
    cameraLookAt: [0, 1.05, 0],
    fov: 42,
    scale: 1.35,
  },
  phonePortrait: {
    cameraPos: [0, 2.2, 7.2],
    cameraLookAt: [0, 1.35, 0],
    fov: 36,
    scale: 1.15,
  },
};

function detectBreakpoint(): Breakpoint {
  if (typeof window === "undefined") return "desktop";
  const w = window.innerWidth;
  const h = window.innerHeight;
  const landscape = w >= h;
  if (w >= 1024 && landscape) return "desktop";
  // Phone portrait is strictly <768px AND taller than wide.
  if (w < 768 && !landscape) return "phonePortrait";
  // Everything else — tablets, and small-landscape phones — gets the
  // tablet treatment per spec.
  return "tablet";
}

/**
 * React hook that tracks the active breakpoint. Uses matchMedia for the
 * three defining boundaries (laptop landscape, phone portrait, generic
 * orientation flip) and a plain resize listener as a safety net. All
 * listeners are torn down on unmount so SPA route changes do not leak
 * handlers.
 */
function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(() => detectBreakpoint());

  useEffect(() => {
    if (typeof window === "undefined") return;
    const update = () => setBp(detectBreakpoint());
    // Sync once in case SSR picked "desktop" but the real viewport is
    // different.
    update();

    window.addEventListener("resize", update);

    const mqlDesktop = window.matchMedia(
      "(min-width: 1024px) and (orientation: landscape)",
    );
    const mqlPhonePortrait = window.matchMedia(
      "(max-width: 767px) and (orientation: portrait)",
    );
    const mqlOrientation = window.matchMedia("(orientation: landscape)");
    mqlDesktop.addEventListener("change", update);
    mqlPhonePortrait.addEventListener("change", update);
    mqlOrientation.addEventListener("change", update);

    return () => {
      window.removeEventListener("resize", update);
      mqlDesktop.removeEventListener("change", update);
      mqlPhonePortrait.removeEventListener("change", update);
      mqlOrientation.removeEventListener("change", update);
    };
  }, []);

  return bp;
}

/**
 * Keeps the Three.js camera in sync with the active breakpoint config.
 * Lives inside <Canvas> so it can call useThree(). Updates position, FOV
 * and lookAt whenever `config` changes (orientation flip, window resize
 * across a breakpoint boundary, etc).
 */
function CameraRig({ config }: { config: BreakpointConfig }) {
  const { camera } = useThree();
  useEffect(() => {
    camera.position.set(
      config.cameraPos[0],
      config.cameraPos[1],
      config.cameraPos[2],
    );
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.fov = config.fov;
    }
    camera.lookAt(
      config.cameraLookAt[0],
      config.cameraLookAt[1],
      config.cameraLookAt[2],
    );
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.updateProjectionMatrix();
    }
  }, [camera, config]);
  return null;
}

type ScreenPoint = { x: number; y: number };

type Placement = {
  /** Feet, in viewport pixels, kept inside the art stage. */
  stand: ScreenPoint;
  /** Point the character turns toward (the active control). */
  look: ScreenPoint;
  /** Marker drawn on the control, off the text the user is editing. */
  pointer: ScreenPoint;
};

/**
 * Place the mesh on the real screen. Feet stay inside the art stage and
 * shift toward the active control. The marker sits on the outer edge of
 * that control so the input itself stays clear.
 */
function placeOnScreen(name: string): Placement | null {
  if (typeof document === "undefined") return null;
  const el = document.querySelector<HTMLElement>(`[data-mascot-target="${name}"]`);
  const stage = document.querySelector<HTMLElement>("[data-mascot-stage]");
  if (!el || !stage) return null;
  const rect = el.getBoundingClientRect();
  const stageRect = stage.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2 || stageRect.width < 2 || stageRect.height < 2) {
    return null;
  }

  const targetX = rect.left + rect.width / 2;
  const targetY = rect.top + rect.height / 2;
  const inset = Math.min(stageRect.width * 0.28, 220);
  const standX = Math.min(
    stageRect.right - inset,
    Math.max(stageRect.left + inset, targetX),
  );
  const standY = stageRect.bottom - Math.min(28, stageRect.height * 0.08);

  const stageOnLeft = stageRect.right <= rect.left + 12;
  const stageAbove = stageRect.bottom <= rect.top + 12;
  const pointer = stageAbove
    ? { x: targetX, y: rect.top - 6 }
    : stageOnLeft
      ? { x: rect.left - 6, y: targetY }
      : { x: rect.left + 16, y: targetY };

  return {
    stand: { x: standX, y: standY },
    look: { x: targetX, y: targetY },
    pointer,
  };
}

/** Feet in the middle of the art stage when the current step has no target. */
function stageHome(): Placement | null {
  if (typeof document === "undefined") return null;
  const stage = document.querySelector<HTMLElement>("[data-mascot-stage]");
  if (!stage) return null;
  const rect = stage.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2) return null;
  const stand = {
    x: rect.left + rect.width / 2,
    y: rect.bottom - Math.min(28, rect.height * 0.08),
  };
  return {
    stand,
    look: { x: stand.x, y: rect.top + rect.height * 0.35 },
    pointer: stand,
  };
}

/** Scale so the 1.8 m mesh fills about 70% of the art stage. */
function scaleForStage(
  stageHeight: number,
  viewportHeight: number,
  config: BreakpointConfig,
): number {
  if (viewportHeight <= 0 || stageHeight <= 0) return config.scale;
  const fov = (config.fov * Math.PI) / 180;
  const visible = 2 * Math.abs(config.cameraPos[2]) * Math.tan(fov / 2);
  const fraction = (stageHeight * 0.7) / viewportHeight;
  const next = (fraction * visible) / 1.8;
  return Math.max(0.55, Math.min(next, config.scale));
}

function useStageBox(step: string | undefined): DOMRect | null {
  const [box, setBox] = useState<DOMRect | null>(() => {
    if (typeof document === "undefined") return null;
    const el = document.querySelector<HTMLElement>("[data-mascot-stage]");
    return el ? el.getBoundingClientRect() : null;
  });
  useEffect(() => {
    const read = () => {
      const el = document.querySelector<HTMLElement>("[data-mascot-stage]");
      setBox(el ? el.getBoundingClientRect() : null);
    };
    read();
    const el = document.querySelector<HTMLElement>("[data-mascot-stage]");
    const observer = el ? new ResizeObserver(read) : null;
    if (el && observer) observer.observe(el);
    window.addEventListener("resize", read);
    window.addEventListener("scroll", read, true);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", read);
      window.removeEventListener("scroll", read, true);
    };
  }, [step]);
  return box;
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
 *   - scale: per-breakpoint scale so the character fills the frame
 *
 * The character's bones animate via useAnimations; we just move the whole
 * group through 3D space and keep it facing its walk direction.
 */
function yawToward(from: THREE.Vector3, to: THREE.Vector3): number | null {
  const dx = to.x - from.x;
  const dz = to.z - from.z;
  if (dx * dx + dz * dz < 1e-4) return null;
  return Math.atan2(dx, dz);
}

function turnToward(group: THREE.Group, yaw: number, delta: number) {
  const current = group.rotation.y;
  const diff = Math.atan2(Math.sin(yaw - current), Math.cos(yaw - current));
  group.rotation.y = current + diff * Math.min(1, delta * 6);
}

function Character({
  targetWorldRef,
  lookWorldRef,
  arrivedRef,
  speed,
  idleClip,
  scale,
}: {
  targetWorldRef: React.MutableRefObject<THREE.Vector3 | null>;
  lookWorldRef: React.MutableRefObject<THREE.Vector3 | null>;
  arrivedRef: React.MutableRefObject<boolean>;
  speed: number;
  idleClip: string;
  scale: number;
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
      const look = lookWorldRef.current;
      const yaw = look ? yawToward(g.position, look) : null;
      if (yaw !== null) turnToward(g, yaw, delta);
      return;
    }
    arrivedRef.current = false;
    setActive(walkClip);
    toTarget.normalize();
    const step = Math.min(dist, speed * delta);
    g.position.add(toTarget.multiplyScalar(step));
    // Face the direction of motion. atan2(x, z) orients +Z-forward meshes.
    turnToward(g, Math.atan2(toTarget.x, toTarget.z), delta);
  });

  // Mascot.glb is about 1.8 m tall. Scale comes from the art stage so
  // the body fills that region. Feet stay at y=0 so ContactShadows
  // render under them.
  return (
    <group ref={group} scale={scale} position={[0, 0, 0]}>
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
  lookWorldRef,
  arrivedRef,
  setPointerPx,
}: {
  tour: string[];
  dwell: number;
  targetWorldRef: React.MutableRefObject<THREE.Vector3 | null>;
  lookWorldRef: React.MutableRefObject<THREE.Vector3 | null>;
  arrivedRef: React.MutableRefObject<boolean>;
  setPointerPx: (p: ScreenPoint | null) => void;
}) {
  const { camera, size } = useThree();
  const indexRef = useRef(0);
  const dwellElapsedRef = useRef(0);
  const lastPointer = useRef<ScreenPoint | null>(null);

  // Reset to the first waypoint whenever the tour changes.
  useEffect(() => {
    indexRef.current = 0;
    dwellElapsedRef.current = 0;
  }, [tour]);

  useFrame((_state, delta) => {
    if (!tour.length) {
      const home = stageHome();
      const viewport = { width: size.width, height: size.height };
      const world = home
        ? screenToGround(home.stand.x, home.stand.y, camera, viewport)
        : null;
      targetWorldRef.current = world;
      lookWorldRef.current = home
        ? screenToGround(home.look.x, home.look.y, camera, viewport)
        : null;
      if (lastPointer.current) {
        lastPointer.current = null;
        setPointerPx(null);
      }
      return;
    }
    const name = tour[indexRef.current % tour.length];
    const named = placeOnScreen(name);
    const placed = named ?? stageHome();
    if (!placed) {
      indexRef.current = (indexRef.current + 1) % tour.length;
      return;
    }
    if (!named) {
      indexRef.current = (indexRef.current + 1) % tour.length;
    }
    const viewport = { width: size.width, height: size.height };
    const world = screenToGround(placed.stand.x, placed.stand.y, camera, viewport);
    const look = screenToGround(placed.look.x, placed.look.y, camera, viewport);
    if (world) targetWorldRef.current = world;
    if (look) {
      lookWorldRef.current = look;
    } else if (world) {
      const dir = Math.sign(placed.look.x - placed.stand.x) || 1;
      lookWorldRef.current = world.clone().add(new THREE.Vector3(dir, 0, 0));
    }
    const prev = lastPointer.current;
    const next = named ? placed.pointer : null;
    const moved = next
      ? !prev || Math.abs(prev.x - next.x) > 2 || Math.abs(prev.y - next.y) > 2
      : prev !== null;
    if (moved) {
      lastPointer.current = next;
      setPointerPx(next);
    }

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

  const breakpoint = useBreakpoint();
  const config = BREAKPOINT_CONFIG[breakpoint];

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

  const tour = STEP_TOURS[step] ?? [];
  const stageBox = useStageBox(step);
  const lookWorldRef = useRef<THREE.Vector3 | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const meshScale = scaleForStage(
    stageBox?.height ?? 0,
    typeof window === "undefined" ? 0 : window.innerHeight,
    config,
  );

  if (!mounted) return null;

  const overlay = (
    <div
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        zIndex: 40,
      }}
    >
      {stageBox && (
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            left: stageBox.left,
            top: stageBox.top,
            width: stageBox.width,
            height: stageBox.height,
            pointerEvents: "none",
            zIndex: 0,
            background:
              "radial-gradient(ellipse 70% 55% at 50% 100%, rgba(11, 34, 56, 0.92) 0%, rgba(11, 34, 56, 0.55) 28%, rgba(11, 34, 56, 0.18) 58%, rgba(11, 34, 56, 0) 78%)",
          }}
        />
      )}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          zIndex: 1,
        }}
      >
        <Canvas
          camera={{ position: config.cameraPos, fov: config.fov }}
          shadows
          dpr={[1, 2]}
          style={{ background: "transparent", pointerEvents: "none" }}
          gl={{ antialias: true, alpha: true, premultipliedAlpha: false }}
        >
          {/* Lighting tuned to make a cream/gold character pop against a
              deep-ocean-blue stage backdrop (see the radial gradient above,
              updated 2026-10-19 at the user's request for bolder contrast).
              Three-point setup:
              - ambientLight 0.75 (was 0.55): a touch brighter base.
              - keyLight (directional, warm) 2.0 (was 1.15) from front-
                right: strong key so the Buddha's bronze reads as gold,
                not beige. Position pulled further out so a bigger
                character (scale 2.0-2.4 per breakpoint) does not blow out.
              - rimLight (directional, cool) 1.8 (was 1.4) from behind-
                left: bumped slightly for the new dark-blue backdrop so
                the cool highlight along the silhouette separates the
                character crisply from the deep ocean blue.
              - hemisphere light with cream-sky / dark-ground: fills in
                shadow sides so the character never goes muddy. */}
          <ambientLight intensity={0.75} />
          <directionalLight
            position={[6, 8, 4]}
            intensity={2.0}
            color={0xfff2d4}
            castShadow
            shadow-mapSize={[1024, 1024]}
          />
          <directionalLight
            position={[-6, 5, -4]}
            intensity={1.8}
            color={0x8ab6ff}
          />
          <hemisphereLight
            color={0xffe8c2}
            groundColor={0x2a1a08}
            intensity={0.5}
          />
          <CameraRig config={config} />
          <Suspense fallback={null}>
            <Character
              targetWorldRef={targetWorldRef}
              lookWorldRef={lookWorldRef}
              arrivedRef={arrivedRef}
              speed={speed}
              idleClip={idleClip}
              scale={meshScale}
            />
            <TourDriver
              tour={tour}
              dwell={dwell}
              targetWorldRef={targetWorldRef}
              lookWorldRef={lookWorldRef}
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
      {pointerPx && (
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            left: pointerPx.x - 14,
            top: pointerPx.y - 14,
            width: 28,
            height: 28,
            pointerEvents: "none",
            zIndex: 2,
            borderRadius: "50%",
            boxShadow:
              "0 0 0 2px rgba(250, 196, 72, 0.9), 0 0 18px 4px rgba(250, 196, 72, 0.45)",
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
    </div>
  );

  return createPortal(overlay, document.body);
}

useGLTF.preload(MODEL_URL);

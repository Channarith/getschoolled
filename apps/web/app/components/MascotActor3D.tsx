"use client";

/**
 * MascotActor3D — real-time 3D animated character with physics, built on
 * React Three Fiber + Rapier. Replaces the CSS-keyframe MascotActor when the
 * `AOEP_MASCOT_3D` flag is on, giving onboarding a video-game-style
 * character instead of a static image with a soft bob.
 *
 * Current character: Fox.glb (Khronos glTF sample, CC-BY-4.0, 160 KB) with
 * three baked clips — Survey (idle), Walk, Run. Scenes map to those clips.
 *
 * To swap in a custom mascot (Buddha-child):
 *   1. Export a rigged .glb from Blender / Mixamo with the same clip names
 *      ("Survey", "Walk", "Run" — or any new names, update CLIP_MAP below).
 *   2. Drop it at apps/web/public/mascot3d/Mascot.glb.
 *   3. Change MODEL_URL to "/mascot3d/Mascot.glb".
 *   4. Tune the character's scale/offset in <Character />.
 *
 * The whole scene is kept offline-usable — the .glb is bundled under
 * apps/web/public, no CDN or external API required at runtime.
 */

import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  useAnimations,
  useGLTF,
} from "@react-three/drei";
import { Physics, RigidBody, type RapierRigidBody } from "@react-three/rapier";
import * as THREE from "three";

import { type MascotScene, poseForAge } from "../lib/mascotPose";
import { applyBuddhaFoxStyle } from "./mascot3d/buddhaFoxStyle";

// Points at the real Meshy character now (v0.70.0 landed Mascot.glb at
// 3.12 MB with 15 Mixamo clips). The old Fox.glb placeholder is retired.
// Note: this component (MascotActor3D) is the legacy 3D-pane renderer and
// is no longer the default - MascotActorChoice defaults to MascotMeshy
// directly, which has the full clip + expression driving logic. This
// path still exists for ?mascot3d=pane users / debug.
const MODEL_URL = "/mascot3d/Mascot.glb";

/**
 * Map each MascotScene kind to a clip name on the loaded glTF. Fox.glb
 * ships Survey / Walk / Run; a custom mascot can expose richer clips
 * (idle, point, dance, read, …) and this map will route them.
 */
const CLIP_MAP: Record<MascotScene["kind"], string> = {
  idle: "Survey",
  "flyin-point": "Walk",
  dance: "Run",
  "age-morph": "Survey",
  video: "Walk",
  teacher: "Walk",
  presentation: "Walk",
  reading: "Survey",
  tutoring: "Walk",
  gaming: "Run",
};

type Props = {
  scene: MascotScene;
  size?: number;
  className?: string;
};

function Character({ scene }: { scene: MascotScene }) {
  const group = useRef<THREE.Group>(null);
  const { scene: gltfScene, animations } = useGLTF(MODEL_URL);
  const { actions, names } = useAnimations(animations, group);

  // Reskin the Fox mesh into the Salareen "Bayon Buddy" aesthetic — stone-
  // tan body + gold lotus crown + gold forehead gem + navy/gold S medallion.
  // Idempotent (gated by a userData flag) so React double-mount in strict
  // mode doesn't duplicate the accessories.
  useEffect(() => {
    if (gltfScene) applyBuddhaFoxStyle(gltfScene);
  }, [gltfScene]);

  // Fox clips in the glTF are literally named Survey / Walk / Run.
  const requestedClip = CLIP_MAP[scene.kind] ?? "Survey";
  const activeClip = useMemo(
    () =>
      names.find((n) => n.toLowerCase() === requestedClip.toLowerCase()) ??
      names[0],
    [names, requestedClip],
  );

  useEffect(() => {
    if (!activeClip) return;
    const action = actions[activeClip];
    if (!action) return;
    action.reset().fadeIn(0.3).play();
    return () => {
      action.fadeOut(0.3);
    };
  }, [actions, activeClip]);

  // The Fox model is unit-metres and tall — scale down for the art pane.
  // age-morph scales smaller for children, bigger for adults.
  const pose = scene.kind === "age-morph" ? poseForAge(scene.age) : null;
  const scaleFactor = pose ? pose.scale : 1.0;
  const BASE = 0.012;

  return (
    <group ref={group} scale={BASE * scaleFactor} position={[0, 0, 0]}>
      <primitive object={gltfScene} />
    </group>
  );
}

/**
 * The character sits in a RigidBody so gravity + light pointer force gives
 * it a subtle bob and lean. For `flyin-point` scenes we push the body
 * horizontally so it slides into frame.
 */
function PhysicsCharacter({ scene }: { scene: MascotScene }) {
  const bodyRef = useRef<RapierRigidBody>(null);

  useEffect(() => {
    const body = bodyRef.current;
    if (!body) return;
    if (scene.kind === "flyin-point") {
      // Nudge the character sideways to simulate flying in.
      const dir = scene.pointAt ?? "down";
      const impulse: Record<string, [number, number, number]> = {
        left: [-0.6, 0.3, 0],
        right: [0.6, 0.3, 0],
        down: [0, 0.6, 0],
        up: [0, 0.6, 0],
      };
      body.applyImpulse({ x: impulse[dir][0], y: impulse[dir][1], z: impulse[dir][2] }, true);
    } else if (scene.kind === "dance") {
      body.applyImpulse({ x: 0, y: 0.8, z: 0 }, true);
    }
  }, [scene]);

  // Gentle idle bob — a small periodic upward impulse so the character
  // never flattens on the ground when idle.
  useFrame(({ clock }) => {
    const body = bodyRef.current;
    if (!body) return;
    if (scene.kind === "idle" || scene.kind === "age-morph" || scene.kind === "reading") {
      const t = clock.getElapsedTime();
      if (Math.sin(t * 2) > 0.95) {
        body.applyImpulse({ x: 0, y: 0.08, z: 0 }, true);
      }
    }
  });

  return (
    <RigidBody
      ref={bodyRef}
      colliders="cuboid"
      linearDamping={0.8}
      angularDamping={0.9}
      position={[0, 0.3, 0]}
      restitution={0.2}
      friction={0.4}
    >
      <Character scene={scene} />
    </RigidBody>
  );
}

export default function MascotActor3D({ scene, size = 260, className }: Props) {
  return (
    <div
      className={className}
      style={{
        width: size,
        height: size,
        pointerEvents: "none",
      }}
      aria-label="Animated 3D mascot"
    >
      <Canvas
        camera={{ position: [0, 1.2, 3.2], fov: 42 }}
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <color attach="background" args={["#0b1020"]} />
        <ambientLight intensity={0.55} />
        <directionalLight
          position={[3, 5, 2]}
          intensity={1.2}
          castShadow
          shadow-mapSize={[1024, 1024]}
        />
        <Suspense fallback={null}>
          <Physics gravity={[0, -9.81, 0]}>
            <PhysicsCharacter scene={scene} />
            {/* Ground plane the character lands on. */}
            <RigidBody type="fixed" friction={1} restitution={0}>
              <mesh
                position={[0, -0.01, 0]}
                rotation={[-Math.PI / 2, 0, 0]}
                receiveShadow
              >
                <planeGeometry args={[10, 10]} />
                <meshStandardMaterial color="#0b1020" />
              </mesh>
            </RigidBody>
          </Physics>
          <ContactShadows
            position={[0, 0, 0]}
            opacity={0.45}
            scale={5}
            blur={2.4}
            far={2}
          />
          <Environment preset="apartment" />
        </Suspense>
      </Canvas>
    </div>
  );
}

// Preload the model so the Suspense fallback is near-instant on step
// transitions after the first mount.
useGLTF.preload(MODEL_URL);

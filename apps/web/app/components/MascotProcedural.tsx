"use client";

/**
 * R3F wrapper around the procedural Buddy mascot (see
 * ./mascot3d/proceduralBuddy.ts and ./mascot3d/faceTexture.ts).
 *
 * Mounts the character in a <Canvas>, drives its animation each frame
 * via useFrame, and lets the parent switch motion state ("idle" / "walk"
 * / "run") and facial expression ("cute" / ... / "mischievous") via
 * props. No .glb load - everything is built from THREE primitives, so
 * there is zero network wait and no WebGL fallback drama.
 *
 * Used by:
 *   - apps/web/app/mascot-lab/page.tsx (standalone demo)
 *   - MascotActorChoice can be extended to route to this when the user
 *     passes ?mascot3d=procedural (future work).
 */

import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  OrbitControls,
} from "@react-three/drei";
import type * as THREE from "three";

import {
  createProceduralBuddy,
  type MotionState,
  type ProceduralBuddy,
} from "./mascot3d/proceduralBuddy";
import type { Expression } from "./mascot3d/faceTexture";

type Props = {
  /** Current facial expression. Hot-swappable. */
  expression: Expression;
  /** Idle / walk / run. */
  motion: MotionState;
  /** Pixel size of the canvas (square). Default 320. */
  size?: number;
  className?: string;
  /** True = show mouse-drag orbit controls (handy in the lab, off in prod). */
  interactive?: boolean;
};

function Buddy({
  expression,
  motion,
}: {
  expression: Expression;
  motion: MotionState;
}) {
  const buddyRef = useRef<ProceduralBuddy | null>(null);
  const groupRef = useRef<THREE.Group | null>(null);

  // Build the character once, on mount. Dispose on unmount.
  const buddy = useMemo(() => {
    const b = createProceduralBuddy(expression);
    buddyRef.current = b;
    return b;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => {
      buddyRef.current?.dispose();
      buddyRef.current = null;
    };
  }, []);

  // Swap expression without rebuilding the character.
  useEffect(() => {
    buddyRef.current?.setExpression(expression);
  }, [expression]);

  // Drive the walk / idle / run cycle every frame.
  useFrame((state) => {
    buddyRef.current?.updateAnimation(motion, state.clock.getElapsedTime());
  });

  // Attach the Three.js group under an R3F primitive wrapper.
  useEffect(() => {
    if (!groupRef.current) return;
    if (!groupRef.current.children.includes(buddy.root)) {
      groupRef.current.add(buddy.root);
    }
    return () => {
      groupRef.current?.remove(buddy.root);
    };
  }, [buddy.root]);

  return <group ref={groupRef} />;
}

export default function MascotProcedural({
  expression,
  motion,
  size = 320,
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
        camera={{ position: [0, 1.3, 3.4], fov: 32 }}
        dpr={[1, 2]}
      >
        {/* Soft warm key light + a cool rim. */}
        <ambientLight intensity={0.55} />
        <directionalLight
          position={[2.5, 4, 3]}
          intensity={1.1}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <directionalLight position={[-3, 2, -2]} intensity={0.3} color="#88aaff" />

        <Buddy expression={expression} motion={motion} />

        <ContactShadows
          position={[0, 0, 0]}
          opacity={0.55}
          scale={5}
          blur={2.4}
          far={2}
        />
        <Environment preset="apartment" />
        {interactive && <OrbitControls enablePan={false} enableZoom={false} />}
      </Canvas>
    </div>
  );
}

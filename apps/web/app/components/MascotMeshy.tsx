"use client";

/**
 * MascotMeshy — renders the real Meshy.ai-generated Bayon Buddy mascot
 * from apps/web/public/mascot3d/Mascot.glb.
 *
 * The GLB is a static mesh (Meshy's image-to-3D path does not rig the
 * character). This component does NOT try to play any animations - if
 * the file eventually gains rigged clips (via the Mixamo + Blender
 * post-processor flow in docs/mascot-pipeline.txt), use MascotActor3D
 * instead. For now we drive a gentle idle bob + slow turn in code so
 * the character does not feel frozen.
 *
 * Lives in its own file so loading the real character does not block
 * the procedural lab (MascotProcedural), and so we can A/B them in the
 * lab page without the two renderers fighting over MODEL_URL.
 */

import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  OrbitControls,
  useGLTF,
} from "@react-three/drei";
import * as THREE from "three";

const MODEL_URL = "/mascot3d/Mascot.glb";

type Props = {
  /** Pixel size of the canvas (square). Default 480. */
  size?: number;
  className?: string;
  /** True = show mouse-drag orbit controls (handy in the lab, off in prod). */
  interactive?: boolean;
  /**
   * Vertical offset in metres applied to the loaded mesh so its feet
   * sit on the ground plane. Meshy exports with its origin usually at
   * the mesh centre; a value of ~0.9 lifts a 1.8 m character so the
   * origin lands at the hips. Defaults to 0 (no shift) - tune per
   * imported model.
   */
  yOffset?: number;
  /**
   * Uniform scale factor. Meshy exports at real-world metres; a
   * mascot that renders too small or too large in the canvas tunes
   * here without re-exporting. Default 1.
   */
  scale?: number;
};

function Character({ yOffset = 0, scale = 1 }: { yOffset?: number; scale?: number }) {
  const groupRef = useRef<THREE.Group>(null);
  const { scene } = useGLTF(MODEL_URL);

  // Clone the scene so React double-mount in strict mode does not try to
  // reuse the same Object3D in two places (R3F will complain loudly).
  const cloned = useMemo(() => scene.clone(true), [scene]);

  // Gentle idle: slow yaw turn + small vertical bob so the character
  // reads as "alive" even though the mesh is static (no rig).
  useFrame((state) => {
    const g = groupRef.current;
    if (!g) return;
    const t = state.clock.getElapsedTime();
    g.rotation.y = Math.sin(t * 0.35) * 0.25;         // ±14° slow sway
    g.position.y = yOffset + Math.sin(t * 1.2) * 0.015; // 1.5 cm breath bob
  });

  return (
    <group ref={groupRef} position={[0, yOffset, 0]} scale={scale}>
      <primitive object={cloned} />
    </group>
  );
}

export default function MascotMeshy({
  size = 480,
  className,
  interactive = false,
  yOffset = 0,
  scale = 1,
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
        {/* Warm key + cool rim - matches the lighting of the procedural
            lab so A/B comparisons are honest. */}
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
          <Character yOffset={yOffset} scale={scale} />
        </Suspense>

        <ContactShadows
          position={[0, 0, 0]}
          opacity={0.55}
          scale={5}
          blur={2.4}
          far={2}
        />
        <Environment preset="apartment" />
        {interactive && <OrbitControls enablePan={false} enableZoom={true} />}
      </Canvas>
    </div>
  );
}

// Preload so the first paint on /mascot-lab is instant.
useGLTF.preload(MODEL_URL);

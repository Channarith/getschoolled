"use client";

/**
 * Procedurally-built "Bayon Buddy" mascot — the Salareen Buddha-kid logo
 * character, in 3D, hand-authored from THREE primitives. No .glb, no
 * .fbx, no Blender needed. Every mesh is a sphere / capsule / cylinder /
 * torus with the sandstone + gold palette from the app icon.
 *
 * Skeleton:
 *
 *     root
 *       ├── body (torso, static)
 *       ├── leftArmPivot ─── rightArmPivot    (rotate at the shoulder)
 *       │     └── forearm        └── forearm   (rotate at the elbow)
 *       │           └── hand           └── hand
 *       ├── leftLegPivot ─── rightLegPivot    (rotate at the hip)
 *       │     └── shin           └── shin      (rotate at the knee)
 *       │           └── foot           └── foot
 *       ├── medallion                           (the S disc, floats at chest)
 *       └── head
 *             ├── face      (plane with CanvasTexture — 8 expressions)
 *             ├── crown     (torus + 6 petals)
 *             └── gem       (icosahedron on the forehead)
 *
 * This is "pseudo-skeletal" — each joint is just a Group whose children
 * are rotated around it. Simpler than a real THREE.SkinnedMesh (which
 * needs per-vertex bone weights) and plenty good for a cartoon mascot.
 *
 * Animation:
 *   - updateAnimation(state, elapsed): called every frame. Rotates the
 *     limb groups based on `state` ("idle" | "walk" | "run").
 *   - setExpression(expr): swaps the face texture. See faceTexture.ts.
 *
 * Rendered inside an R3F <Canvas> via MascotProcedural.tsx.
 */

import * as THREE from "three";

import {
  disposeExpressionTexture,
  expressionTexture,
  type Expression,
} from "./faceTexture";

export type MotionState = "idle" | "walk" | "run";

export interface ProceduralBuddy {
  /** The root Object3D to add to the scene / parent group. */
  root: THREE.Group;
  /** Call every frame with the elapsed seconds; mutates the limb groups. */
  updateAnimation: (state: MotionState, elapsed: number) => void;
  /** Swap the face expression. Disposes the previous CanvasTexture. */
  setExpression: (expr: Expression) => void;
  /** Call when the character leaves the scene — frees GPU allocations. */
  dispose: () => void;
}

// Palette (matches the Buddha-fox skin + the app icon).
const STONE_TAN = new THREE.Color(180 / 255, 140 / 255, 95 / 255);
const STONE_TAN_LIGHT = new THREE.Color(205 / 255, 170 / 255, 125 / 255);
const SALAREEN_GOLD = new THREE.Color(230 / 255, 174 / 255, 54 / 255);
const DEEP_NAVY = new THREE.Color(11 / 255, 16 / 255, 32 / 255);

function stoneMaterial(): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: STONE_TAN,
    roughness: 0.88,
    metalness: 0.03,
  });
}

function stoneLightMaterial(): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: STONE_TAN_LIGHT,
    roughness: 0.85,
    metalness: 0.03,
  });
}

function goldMaterial(): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: SALAREEN_GOLD,
    roughness: 0.4,
    metalness: 0.8,
    emissive: new THREE.Color(0.3, 0.18, 0.05),
    emissiveIntensity: 0.35,
  });
}

function navyMaterial(): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: DEEP_NAVY,
    roughness: 0.6,
    metalness: 0.3,
  });
}

/**
 * Build a left or right arm as a Group that rotates at the shoulder.
 * Positive x = right side of the body in world space.
 */
function buildArm(side: 1 | -1): THREE.Group {
  const shoulder = new THREE.Group();
  shoulder.name = side > 0 ? "rightArmPivot" : "leftArmPivot";

  const upperLen = 0.42;
  const upperArm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.075, 0.065, upperLen, 16),
    stoneMaterial(),
  );
  // Hang the cylinder from the shoulder (pivot at the top end).
  upperArm.position.set(0, -upperLen / 2, 0);
  shoulder.add(upperArm);

  // Elbow is a child of the shoulder, offset to the end of the upper arm.
  const elbow = new THREE.Group();
  elbow.name = side > 0 ? "rightElbow" : "leftElbow";
  elbow.position.set(0, -upperLen, 0);

  const forearmLen = 0.38;
  const forearm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.065, 0.055, forearmLen, 16),
    stoneMaterial(),
  );
  forearm.position.set(0, -forearmLen / 2, 0);
  elbow.add(forearm);

  const hand = new THREE.Mesh(
    new THREE.SphereGeometry(0.07, 16, 12),
    stoneLightMaterial(),
  );
  hand.position.set(0, -forearmLen - 0.02, 0);
  elbow.add(hand);

  shoulder.add(elbow);
  shoulder.userData.elbow = elbow;
  return shoulder;
}

function buildLeg(side: 1 | -1): THREE.Group {
  const hip = new THREE.Group();
  hip.name = side > 0 ? "rightLegPivot" : "leftLegPivot";

  const thighLen = 0.46;
  const thigh = new THREE.Mesh(
    new THREE.CylinderGeometry(0.09, 0.08, thighLen, 16),
    stoneMaterial(),
  );
  thigh.position.set(0, -thighLen / 2, 0);
  hip.add(thigh);

  const knee = new THREE.Group();
  knee.name = side > 0 ? "rightKnee" : "leftKnee";
  knee.position.set(0, -thighLen, 0);

  const shinLen = 0.42;
  const shin = new THREE.Mesh(
    new THREE.CylinderGeometry(0.08, 0.07, shinLen, 16),
    stoneMaterial(),
  );
  shin.position.set(0, -shinLen / 2, 0);
  knee.add(shin);

  const foot = new THREE.Mesh(
    new THREE.BoxGeometry(0.14, 0.07, 0.22),
    stoneLightMaterial(),
  );
  // Foot sits in front of the ankle so forward is +z.
  foot.position.set(0, -shinLen - 0.03, 0.06);
  knee.add(foot);

  hip.add(knee);
  hip.userData.knee = knee;
  return hip;
}

function buildTorso(): THREE.Mesh {
  // Short wide capsule for a chubby toddler-proportioned body.
  const torso = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.28, 0.3, 8, 16),
    stoneMaterial(),
  );
  torso.name = "torso";
  return torso;
}

function buildHead(): { group: THREE.Group; faceMesh: THREE.Mesh } {
  const headGroup = new THREE.Group();
  headGroup.name = "head";

  // Round oversized head (toddler proportions, ~1:2 head-to-body).
  const skull = new THREE.Mesh(
    new THREE.SphereGeometry(0.36, 32, 24),
    stoneMaterial(),
  );
  headGroup.add(skull);

  // Face plane sits a hair in front of the sphere so the CanvasTexture
  // reads crisply. We use a MeshBasicMaterial so the face doesn't darken
  // with the scene lights (keeps it readable at low contrast too).
  const faceMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(0.56, 0.56),
    new THREE.MeshBasicMaterial({
      transparent: true,
      side: THREE.FrontSide,
      depthWrite: false,
    }),
  );
  faceMesh.name = "face";
  faceMesh.position.set(0, 0.02, 0.345);
  headGroup.add(faceMesh);

  // Lotus crown (same recipe as buddhaFoxStyle.ts but tuned for this scale).
  const crownRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.3, 0.045, 12, 32),
    goldMaterial(),
  );
  crownRing.position.set(0, 0.32, 0);
  crownRing.rotation.x = Math.PI / 2;
  headGroup.add(crownRing);

  const PETALS = 6;
  for (let i = 0; i < PETALS; i++) {
    const petal = new THREE.Mesh(
      new THREE.ConeGeometry(0.07, 0.18, 12),
      goldMaterial(),
    );
    const angle = (i / PETALS) * Math.PI * 2;
    petal.position.set(Math.cos(angle) * 0.3, 0.4, Math.sin(angle) * 0.3);
    petal.lookAt(petal.position.x * 2, petal.position.y + 0.25, petal.position.z * 2);
    headGroup.add(petal);
  }

  // Forehead gem.
  const gem = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.045, 0),
    new THREE.MeshStandardMaterial({
      color: SALAREEN_GOLD,
      metalness: 0.9,
      roughness: 0.2,
      emissive: SALAREEN_GOLD,
      emissiveIntensity: 0.9,
    }),
  );
  gem.position.set(0, 0.28, 0.34);
  headGroup.add(gem);

  return { group: headGroup, faceMesh };
}

function buildMedallion(): THREE.Group {
  const g = new THREE.Group();
  g.name = "medallion";

  const disc = new THREE.Mesh(
    new THREE.CircleGeometry(0.16, 48),
    navyMaterial(),
  );
  disc.rotation.y = 0;
  g.add(disc);

  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(0.16, 0.015, 10, 48),
    goldMaterial(),
  );
  g.add(ring);

  // The "S" — procedurally built from two arcs, kept inside the ring.
  const sShape = new THREE.Shape();
  const R = 0.085;
  const T = 0.028;
  sShape.absarc(0, R, R, Math.PI, 0, false);
  sShape.absarc(0, -R, R, 0, Math.PI, false);
  const hole = new THREE.Path();
  hole.absarc(0, R, R - T, Math.PI, 0, false);
  hole.absarc(0, -R, R - T, 0, Math.PI, false);
  sShape.holes.push(hole);
  const sMesh = new THREE.Mesh(
    new THREE.ExtrudeGeometry(sShape, { depth: 0.012, bevelEnabled: false }),
    goldMaterial(),
  );
  sMesh.position.set(0, 0, 0.006);
  g.add(sMesh);

  return g;
}

/**
 * Build a complete procedural Buddy character.
 *
 * The returned object exposes imperative controls (updateAnimation,
 * setExpression) rather than React state — that way the R3F component
 * can call them from useFrame without triggering a React re-render for
 * every tick.
 */
export function createProceduralBuddy(initialExpression: Expression = "cute"): ProceduralBuddy {
  const root = new THREE.Group();
  root.name = "proceduralBuddy";

  // Torso sits at origin; everything else hangs off it.
  const torso = buildTorso();
  root.add(torso);

  // Arms attach to the top sides of the torso.
  const leftArm = buildArm(-1);
  leftArm.position.set(-0.32, 0.2, 0);
  root.add(leftArm);
  const rightArm = buildArm(1);
  rightArm.position.set(0.32, 0.2, 0);
  root.add(rightArm);

  // Legs attach to the bottom of the torso.
  const leftLeg = buildLeg(-1);
  leftLeg.position.set(-0.14, -0.2, 0);
  root.add(leftLeg);
  const rightLeg = buildLeg(1);
  rightLeg.position.set(0.14, -0.2, 0);
  root.add(rightLeg);

  // Medallion in front of the chest.
  const medallion = buildMedallion();
  medallion.position.set(0, 0.03, 0.3);
  root.add(medallion);

  // Head on top of torso.
  const { group: head, faceMesh } = buildHead();
  head.position.set(0, 0.68, 0);
  root.add(head);

  // ---- face expression state ----
  let currentExpression: Expression = initialExpression;
  let currentTexture: THREE.CanvasTexture | null = null;
  const faceMaterial = faceMesh.material as THREE.MeshBasicMaterial;

  function applyExpression(expr: Expression): void {
    const next = expressionTexture(expr);
    disposeExpressionTexture(currentTexture);
    currentTexture = next;
    faceMaterial.map = next;
    faceMaterial.needsUpdate = true;
    currentExpression = expr;
  }

  applyExpression(initialExpression);

  // ---- animation ----
  const BASE_Y = 0.9;        // torso resting height (feet at y ~= 0)
  root.position.y = BASE_Y;

  function updateAnimation(state: MotionState, elapsed: number): void {
    // Walk ~1 Hz, run ~2 Hz, idle gentle breath ~0.5 Hz.
    if (state === "walk" || state === "run") {
      const freq = state === "run" ? 3.2 : 1.6;
      const amp = state === "run" ? 0.85 : 0.6;
      const phase = elapsed * freq * Math.PI * 2;
      const s = Math.sin(phase);

      // Legs alternate.
      leftLeg.rotation.x = s * amp;
      rightLeg.rotation.x = -s * amp;
      // Knees bend when the leg kicks forward (positive rot.x).
      const leftKnee = leftLeg.userData.knee as THREE.Group;
      const rightKnee = rightLeg.userData.knee as THREE.Group;
      leftKnee.rotation.x = Math.max(0, -s) * amp * 0.9;
      rightKnee.rotation.x = Math.max(0, s) * amp * 0.9;

      // Arms counter-swing.
      leftArm.rotation.x = -s * amp * 0.75;
      rightArm.rotation.x = s * amp * 0.75;
      // Slight elbow bend on the back-swing.
      const leftElbow = leftArm.userData.elbow as THREE.Group;
      const rightElbow = rightArm.userData.elbow as THREE.Group;
      leftElbow.rotation.x = Math.max(0, s) * 0.4;
      rightElbow.rotation.x = Math.max(0, -s) * 0.4;

      // Vertical bob (two bobs per full cycle — one per footfall).
      root.position.y = BASE_Y + Math.abs(Math.sin(phase)) * (state === "run" ? 0.08 : 0.04);

      // Slight torso twist for liveness.
      torso.rotation.y = s * 0.08;
      head.rotation.y = -s * 0.05;
    } else {
      // Idle: slow breath + gentle sway. Arms rest at sides, legs straight.
      const breath = Math.sin(elapsed * 1.2);
      root.position.y = BASE_Y + breath * 0.015;
      torso.rotation.y = 0;
      leftLeg.rotation.x = 0;
      rightLeg.rotation.x = 0;
      (leftLeg.userData.knee as THREE.Group).rotation.x = 0;
      (rightLeg.userData.knee as THREE.Group).rotation.x = 0;
      leftArm.rotation.x = 0;
      rightArm.rotation.x = 0;
      // Hands fold slightly forward (toward the medallion), reading as the
      // kneeling-with-medallion silhouette from the app icon.
      leftArm.rotation.z = 0.25;
      rightArm.rotation.z = -0.25;
      (leftArm.userData.elbow as THREE.Group).rotation.x = 1.1;
      (rightArm.userData.elbow as THREE.Group).rotation.x = 1.1;
      // Head: slow look around.
      head.rotation.y = Math.sin(elapsed * 0.4) * 0.15;
      head.rotation.x = Math.sin(elapsed * 0.3) * 0.05;
    }
  }

  function setExpression(expr: Expression): void {
    if (expr === currentExpression) return;
    applyExpression(expr);
  }

  function dispose(): void {
    disposeExpressionTexture(currentTexture);
    root.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        const mat = obj.material;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else mat.dispose();
      }
    });
  }

  return { root, updateAnimation, setExpression, dispose };
}

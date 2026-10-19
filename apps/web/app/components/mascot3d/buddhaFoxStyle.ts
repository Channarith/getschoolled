/**
 * buddhaFoxStyle — reskins the Khronos Fox.glb into a stone-Buddha-style
 * fox spirit mascot, so the 3D character matches our Salareen "Bayon Buddy"
 * aesthetic without changing meshes, rigs, or animations.
 *
 * What it does to the loaded glTF scene:
 *   1. Replaces every mesh's material with a warm sandstone-tan
 *      MeshStandardMaterial (matches docs/screens/aiclassroom_logo.png body
 *      palette ≈ RGB 180, 140, 95; rough and matte like carved stone).
 *   2. Attaches these accessories above the character:
 *        - a floating gold lotus-ring crown (TorusGeometry) that bobs with
 *          the body because it rides the existing skeleton transform
 *        - a small glowing emissive forehead gem (ico Sphere, warm gold)
 *        - a Pali-S medallion dangling in front of the chest
 *   3. Marks the whole thing cast + receive shadow for the ContactShadows
 *      pass below the Canvas.
 *
 * To replace this styling with a real Buddha-child rigged .glb later:
 *   - drop the new rigged glb at apps/web/public/mascot3d/Mascot.glb
 *   - change MODEL_URL to "/mascot3d/Mascot.glb"
 *   - stop calling applyBuddhaFoxStyle() in your <Character /> component
 *
 * Pure Three.js — no React. Safe to call once per glTF load.
 */

import * as THREE from "three";

// Sandstone tan sampled from the mascot's body — same palette as
// docs/screens/aiclassroom_logo.png (knee highlight ≈ 220/180/130;
// mid-tone ≈ 180/140/95; shadow ≈ 110/80/40).
const STONE_TAN = new THREE.Color(180 / 255, 140 / 255, 95 / 255);
// Warm medallion gold.
const SALAREEN_GOLD = new THREE.Color(230 / 255, 174 / 255, 54 / 255);
// Deep navy — matches the medallion disc background.
const DEEP_NAVY = new THREE.Color(11 / 255, 16 / 255, 32 / 255);

/**
 * The Khronos Fox model's root bounding box top is roughly at y ≈ 1.2
 * before scaling. These offsets are tuned for the 0.012 scale factor used
 * in MascotActor3D / MascotOverlay3D and are expressed in the ORIGINAL
 * (pre-scale) coordinate space so they ride the mesh's own transform.
 */
const CROWN_Y_OFFSET = 80; // just above the ears
const CROWN_RADIUS = 24;
const CROWN_TUBE_RADIUS = 4.5;

const GEM_Y_OFFSET = 60; // forehead level
const GEM_FORWARD = 18; // nudged toward the muzzle
const GEM_RADIUS = 3.2;

const MEDALLION_Y_OFFSET = -5; // dangling at chest level
const MEDALLION_FORWARD = 18;
const MEDALLION_RADIUS = 10;

/**
 * Build + attach the Buddha accessories to the given root. Idempotent:
 * if the accessories are already attached (userData flag), we skip.
 */
function attachAccessories(root: THREE.Object3D): void {
  if ((root.userData as Record<string, unknown>).aoepBuddhaAccessoriesAttached) {
    return;
  }
  (root.userData as Record<string, unknown>).aoepBuddhaAccessoriesAttached = true;

  // Lotus crown — a thick gold ring sitting above the head.
  const crownGeom = new THREE.TorusGeometry(CROWN_RADIUS, CROWN_TUBE_RADIUS, 20, 64);
  const crownMat = new THREE.MeshStandardMaterial({
    color: SALAREEN_GOLD,
    metalness: 0.75,
    roughness: 0.22,
    emissive: SALAREEN_GOLD.clone().multiplyScalar(0.15),
  });
  const crown = new THREE.Mesh(crownGeom, crownMat);
  crown.rotation.x = Math.PI / 2;
  crown.position.set(0, CROWN_Y_OFFSET, 0);
  crown.castShadow = true;
  crown.receiveShadow = true;
  crown.name = "aoep-buddha-crown";
  root.add(crown);

  // Six small lotus petals around the crown — simple cones evenly spaced.
  const petalMat = new THREE.MeshStandardMaterial({
    color: SALAREEN_GOLD,
    metalness: 0.65,
    roughness: 0.28,
  });
  for (let i = 0; i < 6; i++) {
    const petal = new THREE.Mesh(
      new THREE.ConeGeometry(3.2, 10, 10),
      petalMat,
    );
    const a = (i / 6) * Math.PI * 2;
    petal.position.set(
      Math.cos(a) * CROWN_RADIUS,
      CROWN_Y_OFFSET + 6,
      Math.sin(a) * CROWN_RADIUS,
    );
    // Petals tilt outward so they frame the crown.
    petal.rotation.x = -0.25;
    petal.lookAt(root.position.x, CROWN_Y_OFFSET + 20, root.position.z);
    crown.add(petal);
  }

  // Forehead gem — small emissive sphere above the eyes.
  const gem = new THREE.Mesh(
    new THREE.IcosahedronGeometry(GEM_RADIUS, 1),
    new THREE.MeshStandardMaterial({
      color: SALAREEN_GOLD,
      metalness: 0.3,
      roughness: 0.15,
      emissive: SALAREEN_GOLD.clone().multiplyScalar(0.9),
      emissiveIntensity: 0.9,
    }),
  );
  gem.position.set(0, GEM_Y_OFFSET, GEM_FORWARD);
  gem.name = "aoep-buddha-gem";
  gem.castShadow = true;
  root.add(gem);

  // "S" medallion dangling at the chest — a navy disc with a gold ring.
  // Using CircleGeometry (disc) + TorusGeometry (ring) + simple TextureS.
  const medallionGroup = new THREE.Group();
  medallionGroup.name = "aoep-buddha-medallion";
  medallionGroup.position.set(0, MEDALLION_Y_OFFSET, MEDALLION_FORWARD);

  const disc = new THREE.Mesh(
    new THREE.CircleGeometry(MEDALLION_RADIUS, 48),
    new THREE.MeshStandardMaterial({
      color: DEEP_NAVY,
      roughness: 0.65,
      metalness: 0.1,
    }),
  );
  disc.castShadow = true;
  medallionGroup.add(disc);

  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(MEDALLION_RADIUS, 1.2, 10, 40),
    new THREE.MeshStandardMaterial({
      color: SALAREEN_GOLD,
      metalness: 0.75,
      roughness: 0.25,
    }),
  );
  ring.castShadow = true;
  medallionGroup.add(ring);

  // A chunky letter "S" rendered as extruded shape — procedural so no
  // font file is needed. The shape is a stylised Salareen S built from
  // two concentric arcs + mid stroke.
  const sShape = new THREE.Shape();
  const r = MEDALLION_RADIUS * 0.6;
  // Top arc of the S (left-to-right).
  sShape.moveTo(-r * 0.6, r * 0.7);
  sShape.quadraticCurveTo(-r * 1.1, r * 1.1, 0, r * 1.1);
  sShape.quadraticCurveTo(r * 1.1, r * 1.1, r * 1.1, r * 0.5);
  sShape.quadraticCurveTo(r * 1.1, -r * 0.1, 0, -r * 0.1);
  sShape.quadraticCurveTo(-r * 1.1, -r * 0.1, -r * 1.1, -r * 0.5);
  sShape.quadraticCurveTo(-r * 1.1, -r * 1.1, 0, -r * 1.1);
  sShape.quadraticCurveTo(r * 1.1, -r * 1.1, r * 0.6, -r * 0.7);

  const sGeom = new THREE.ExtrudeGeometry(sShape, {
    depth: 0.9,
    bevelEnabled: true,
    bevelThickness: 0.3,
    bevelSize: 0.3,
    bevelSegments: 2,
  });
  const sMat = new THREE.MeshStandardMaterial({
    color: SALAREEN_GOLD,
    metalness: 0.8,
    roughness: 0.2,
  });
  const sMesh = new THREE.Mesh(sGeom, sMat);
  sMesh.scale.setScalar(0.55);
  sMesh.position.z = 0.3;
  sMesh.castShadow = true;
  medallionGroup.add(sMesh);

  root.add(medallionGroup);
}

/**
 * Apply the Buddha-fox skin to a glTF scene group. Walks every child
 * mesh, substitutes its material for the sandstone tan, and attaches
 * the gold crown / gem / medallion accessories to the root.
 *
 * Returns the same `root` for convenient chaining.
 */
export function applyBuddhaFoxStyle<T extends THREE.Object3D>(root: T): T {
  const stoneMaterial = new THREE.MeshStandardMaterial({
    color: STONE_TAN,
    roughness: 0.88,
    metalness: 0.03,
    // A hint of darkening in the deep crevices from a subtle ambient
    // occlusion tint (no AO map here — we just lean on roughness and the
    // ContactShadows pass).
  });
  root.traverse((child) => {
    if ((child as THREE.Mesh).isMesh) {
      const mesh = child as THREE.Mesh;
      // Preserve bone-skinning: we clone the stone material per mesh so
      // SkinnedMesh skinning uniforms are set up fresh.
      mesh.material = stoneMaterial.clone();
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    }
  });
  attachAccessories(root);
  return root;
}

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { GLTFExporter } from "three/addons/exporters/GLTFExporter.js";

const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, "..", "src", "theodore_course_studio", "avatar_static");
fs.mkdirSync(dist, { recursive: true });
fs.mkdirSync(path.join(dist, "utils"), { recursive: true });
fs.mkdirSync(path.join(dist, "loaders"), { recursive: true });

// GLTFExporter uses browser FileReader even when exporting an ArrayBuffer.
globalThis.FileReader = class {
  result = null;
  onloadend = null;
  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then((value) => {
      this.result = value;
      if (this.onloadend) this.onloadend();
    });
  }
  readAsDataURL(blob) {
    blob.arrayBuffer().then((value) => {
      this.result = `data:${blob.type};base64,${Buffer.from(value).toString("base64")}`;
      if (this.onloadend) this.onloadend();
    });
  }
};

const scene = new THREE.Scene();
scene.name = "TheodoreAvatar";
const rootRig = new THREE.Group();
rootRig.name = "AvatarRoot";
scene.add(rootRig);

const stone = new THREE.MeshStandardMaterial({
  name: "HologramStone",
  color: 0x7ce9ff,
  emissive: 0x116b84,
  emissiveIntensity: 0.45,
  roughness: 0.62,
  metalness: 0.04,
  transparent: true,
  opacity: 0.72,
  depthWrite: false,
});
const gold = new THREE.MeshStandardMaterial({
  name: "CrownGold",
  color: 0xf2d07a,
  emissive: 0x5f4210,
  emissiveIntensity: 0.35,
  roughness: 0.55,
  metalness: 0.3,
  transparent: true,
  opacity: 0.78,
  depthWrite: false,
});
const dark = new THREE.MeshStandardMaterial({
  name: "Features",
  color: 0x183946,
  emissive: 0x0b2430,
  emissiveIntensity: 0.25,
  roughness: 0.8,
  transparent: true,
  opacity: 0.88,
  depthWrite: false,
});

function mesh(name, geometry, material, parent, position = [0, 0, 0], scale = [1, 1, 1]) {
  const value = new THREE.Mesh(geometry, material);
  value.name = name;
  value.position.set(...position);
  value.scale.set(...scale);
  value.castShadow = false;
  value.receiveShadow = false;
  parent.add(value);
  return value;
}

function joint(name, parent, position) {
  const value = new THREE.Group();
  value.name = name;
  value.position.set(...position);
  parent.add(value);
  return value;
}

function limb(name, parent, length, radius, position = [0, 0, 0]) {
  return mesh(
    name,
    new THREE.CapsuleGeometry(radius, Math.max(0.01, length - radius * 2), 6, 12),
    stone,
    parent,
    position,
  );
}

const hips = joint("Hips", rootRig, [0, 2.15, 0]);
mesh("Pelvis", new THREE.SphereGeometry(0.42, 20, 14), stone, hips, [0, 0.05, 0], [1.2, 0.72, 0.75]);
const spine = joint("Spine", hips, [0, 0.34, 0]);
mesh("Torso", new THREE.CapsuleGeometry(0.38, 0.68, 8, 18), stone, spine, [0, 0.42, 0], [1.13, 1, 0.72]);
const chest = joint("Chest", spine, [0, 0.78, 0]);
const neck = joint("Neck", chest, [0, 0.34, 0]);
limb("NeckMesh", neck, 0.24, 0.12, [0, 0.08, 0]);
const head = joint("Head", neck, [0, 0.28, 0]);
mesh("HeadMesh", new THREE.SphereGeometry(0.43, 28, 20), stone, head, [0, 0.28, 0], [0.93, 1.08, 0.86]);

// Salareen identity: broad ears, soft cheeks, calm eyes, and Bayon-style crown.
const leftEar = joint("LeftEar", head, [-0.42, 0.3, 0]);
mesh("LeftEarMesh", new THREE.SphereGeometry(0.15, 16, 12), stone, leftEar, [0, 0, 0], [0.58, 1, 0.36]);
const rightEar = joint("RightEar", head, [0.42, 0.3, 0]);
mesh("RightEarMesh", new THREE.SphereGeometry(0.15, 16, 12), stone, rightEar, [0, 0, 0], [0.58, 1, 0.36]);
mesh("LeftCheek", new THREE.SphereGeometry(0.13, 12, 8), stone, head, [-0.2, 0.18, 0.36], [1, 0.58, 0.42]);
mesh("RightCheek", new THREE.SphereGeometry(0.13, 12, 8), stone, head, [0.2, 0.18, 0.36], [1, 0.58, 0.42]);
const leftEye = joint("LeftEye", head, [-0.16, 0.37, 0.37]);
const rightEye = joint("RightEye", head, [0.16, 0.37, 0.37]);
mesh("LeftEyeMesh", new THREE.SphereGeometry(0.055, 12, 8), dark, leftEye, [0, 0, 0], [1.25, 0.38, 0.5]);
mesh("RightEyeMesh", new THREE.SphereGeometry(0.055, 12, 8), dark, rightEye, [0, 0, 0], [1.25, 0.38, 0.5]);
const leftBrow = joint("LeftBrow", head, [-0.16, 0.47, 0.385]);
const rightBrow = joint("RightBrow", head, [0.16, 0.47, 0.385]);
mesh("LeftBrowMesh", new THREE.BoxGeometry(0.15, 0.025, 0.025), dark, leftBrow);
mesh("RightBrowMesh", new THREE.BoxGeometry(0.15, 0.025, 0.025), dark, rightBrow);

const jaw = joint("Jaw", head, [0, 0.08, 0.34]);
const mouthGeometry = new THREE.SphereGeometry(0.105, 16, 10);
const basePosition = mouthGeometry.attributes.position;
const open = new Float32Array(basePosition.count * 3);
const wide = new Float32Array(basePosition.count * 3);
for (let i = 0; i < basePosition.count; i += 1) {
  const x = basePosition.getX(i);
  const y = basePosition.getY(i);
  const z = basePosition.getZ(i);
  open[i * 3] = x * 0.72;
  open[i * 3 + 1] = y * 1.55 - 0.018;
  open[i * 3 + 2] = z;
  wide[i * 3] = x * 1.55;
  wide[i * 3 + 1] = y * 0.55;
  wide[i * 3 + 2] = z;
}
mouthGeometry.morphAttributes.position = [
  new THREE.Float32BufferAttribute(open, 3),
  new THREE.Float32BufferAttribute(wide, 3),
];
const mouth = mesh("Mouth", mouthGeometry, dark, jaw, [0, 0, 0], [1, 0.34, 0.38]);
mouth.morphTargetDictionary = { mouthOpen: 0, mouthWide: 1 };
mouth.morphTargetInfluences = [0, 0];

const crown = joint("Crown", head, [0, 0.76, 0]);
mesh("CrownBand", new THREE.CylinderGeometry(0.32, 0.38, 0.19, 16), gold, crown);
mesh("CrownLotus", new THREE.ConeGeometry(0.21, 0.42, 8), gold, crown, [0, 0.28, 0]);
for (let i = 0; i < 5; i += 1) {
  const a = (i / 5) * Math.PI * 2;
  mesh(
    `CrownPetal${i}`,
    new THREE.ConeGeometry(0.075, 0.22, 6),
    gold,
    crown,
    [Math.sin(a) * 0.25, 0.15, Math.cos(a) * 0.18],
    [1, 1, 0.6],
  );
}

function arm(side) {
  const sign = side === "Left" ? -1 : 1;
  const shoulder = joint(`${side}Shoulder`, chest, [sign * 0.45, 0.18, 0]);
  shoulder.rotation.z = sign * -0.08;
  limb(`${side}UpperArm`, shoulder, 0.62, 0.13, [0, -0.28, 0]);
  const elbow = joint(`${side}Elbow`, shoulder, [0, -0.62, 0]);
  limb(`${side}ForeArm`, elbow, 0.58, 0.11, [0, -0.26, 0]);
  const wrist = joint(`${side}Wrist`, elbow, [0, -0.58, 0]);
  mesh(`${side}Hand`, new THREE.SphereGeometry(0.14, 14, 10), stone, wrist, [0, -0.08, 0], [0.72, 1.15, 0.44]);
  const fingers = joint(`${side}Fingers`, wrist, [0, -0.19, 0]);
  for (let i = 0; i < 4; i += 1) {
    limb(`${side}Finger${i}`, fingers, 0.16, 0.023, [(i - 1.5) * 0.04, -0.07, 0]);
  }
  return { shoulder, elbow, wrist, fingers };
}

function leg(side) {
  const sign = side === "Left" ? -1 : 1;
  const hip = joint(`${side}Hip`, hips, [sign * 0.23, -0.05, 0]);
  limb(`${side}Thigh`, hip, 0.83, 0.17, [0, -0.38, 0]);
  const knee = joint(`${side}Knee`, hip, [0, -0.82, 0]);
  limb(`${side}Shin`, knee, 0.78, 0.14, [0, -0.35, 0]);
  const ankle = joint(`${side}Ankle`, knee, [0, -0.76, 0]);
  mesh(`${side}Foot`, new THREE.CapsuleGeometry(0.13, 0.25, 6, 12), stone, ankle, [0, -0.04, 0.12], [0.95, 0.65, 1.42]);
  return { hip, knee, ankle };
}

arm("Left");
arm("Right");
leg("Left");
leg("Right");

// A small chest mark ties Theodore to the Salareen mark without using a flat texture.
const mark = joint("SalareenMark", chest, [0, 0.18, 0.36]);
const markCurve = new THREE.EllipseCurve(0, 0, 0.13, 0.13, 0, Math.PI * 1.65, false, 0.2);
const markPoints = markCurve.getPoints(24).map((p) => new THREE.Vector3(p.x, p.y, 0));
mesh("MarkRing", new THREE.TubeGeometry(new THREE.CatmullRomCurve3(markPoints), 32, 0.018, 6, false), gold, mark);

rootRig.position.y = -0.48;
scene.traverse((value) => {
  if (value.isMesh) {
    value.userData.avatarPart = true;
  }
});

const exporter = new GLTFExporter();
const binary = await new Promise((resolve, reject) => {
  exporter.parse(
    scene,
    (result) => resolve(result),
    (error) => reject(error),
    { binary: true, onlyVisible: true },
  );
});
fs.writeFileSync(path.join(dist, "theodore.glb"), Buffer.from(binary));

for (const [source, target] of [
  ["node_modules/three/build/three.module.js", "three.module.js"],
  ["node_modules/three/examples/jsm/loaders/GLTFLoader.js", "loaders/GLTFLoader.js"],
  ["node_modules/three/examples/jsm/utils/BufferGeometryUtils.js", "utils/BufferGeometryUtils.js"],
]) {
  fs.copyFileSync(path.join(root, source), path.join(dist, target));
}
fs.copyFileSync(path.join(root, "avatar_runtime.js"), path.join(dist, "avatar_runtime.js"));
console.log(`Wrote Theodore avatar assets to ${dist}`);

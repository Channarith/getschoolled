/**
 * Reports the exported presenter proportions straight from the GLB, so a canon
 * change (head-to-body ratio, lean, rig) is verifiable without opening a browser.
 * Usage: node inspect_avatar.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, "..", "src", "theodore_course_studio", "avatar_static");

function readGlb(file) {
  const buf = fs.readFileSync(file);
  const jsonLength = buf.readUInt32LE(12);
  const json = JSON.parse(buf.slice(20, 20 + jsonLength).toString("utf8"));
  const binStart = 20 + jsonLength + 8;
  return { json, bin: buf.slice(binStart) };
}

/** Reads a float32 vec3 accessor out of the GLB binary chunk. */
function readVec3(json, bin, accessorIndex) {
  const acc = json.accessors[accessorIndex];
  const view = json.bufferViews[acc.bufferView];
  const base = (view.byteOffset || 0) + (acc.byteOffset || 0);
  const stride = view.byteStride || 12;
  const out = new Float32Array(acc.count * 3);
  for (let i = 0; i < acc.count; i += 1) {
    const at = base + i * stride;
    out[i * 3] = bin.readFloatLE(at);
    out[i * 3 + 1] = bin.readFloatLE(at + 4);
    out[i * 3 + 2] = bin.readFloatLE(at + 8);
  }
  return out;
}

const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

/** Column-major 4x4 multiply, matching glTF's node.matrix layout. */
function multiply(a, b) {
  const out = new Array(16).fill(0);
  for (let col = 0; col < 4; col += 1) {
    for (let row = 0; row < 4; row += 1) {
      let sum = 0;
      for (let k = 0; k < 4; k += 1) sum += a[k * 4 + row] * b[col * 4 + k];
      out[col * 4 + row] = sum;
    }
  }
  return out;
}

function localMatrix(node) {
  if (node.matrix) return node.matrix;
  const t = node.translation || [0, 0, 0];
  const m = IDENTITY.slice();
  m[12] = t[0];
  m[13] = t[1];
  m[14] = t[2];
  return m;
}

function meshBounds(json, meshIndex) {
  const mesh = json.meshes[meshIndex];
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const prim of mesh.primitives || []) {
    const acc = json.accessors[prim.attributes.POSITION];
    if (!acc?.min) continue;
    for (let i = 0; i < 3; i += 1) {
      min[i] = Math.min(min[i], acc.min[i]);
      max[i] = Math.max(max[i], acc.max[i]);
    }
  }
  return { min, max };
}

let failures = 0;

for (const file of ["presenter_female.glb", "presenter_male.glb"]) {
  const { json, bin } = readGlb(path.join(dist, file));
  const nodes = json.nodes || [];
  const world = new Map();

  const walk = (index, parent) => {
    const node = nodes[index];
    const m = multiply(parent, localMatrix(node));
    world.set(node.name, { matrix: m, node });
    for (const child of node.children || []) walk(child, m);
  };
  for (const sceneNode of json.scenes?.[0]?.nodes || []) walk(sceneNode, IDENTITY);

  const pos = (name) => {
    const entry = world.get(name);
    return entry ? [entry.matrix[12], entry.matrix[13], entry.matrix[14]] : null;
  };

  // The skinned body's POSITION is authored in bind (world) space, so it alone
  // gives the true silhouette; feature meshes are in bone-local space.
  const bodyNode = world.get("PresenterBody")?.node;
  const { min, max } = meshBounds(json, bodyNode.mesh);
  const height = max[1] - min[1];
  // The chin is a sculpted point on the head mesh, not a bone, so the builder
  // publishes it; measuring from the Jaw pivot would overstate the ratio.
  const canon = json.scenes?.[0]?.extras?.presenter || {};
  const skull = max[1] - canon.chinY;

  console.log(`\n=== ${file} (${json.scenes?.[0]?.name || "scene"}) ===`);
  console.log(`  height (body mesh)   ${height.toFixed(3)}  (top ${max[1].toFixed(3)}, floor ${min[1].toFixed(3)})`);
  console.log(`  skull (chin->top)    ${skull.toFixed(3)}  => ${(max[1] / skull).toFixed(2)} heads tall (canon ${canon.heads})`);
  console.log(`  shoulder width       ${(max[0] - min[0]).toFixed(3)}`);
  console.log(`  bone count           ${json.skins?.[0]?.joints?.length ?? 0}`);
  console.log("  forward lean (world z):");
  for (const name of ["Hips", "Spine", "Chest", "Neck", "Head", "LeftWrist"]) {
    const p = pos(name);
    if (p) console.log(`    ${name.padEnd(10)} y=${p[1].toFixed(2)}  z=${p[2].toFixed(4)}`);
  }
  const missing = [
    "Jaw", "Crown", "LeftEye", "RightEye", "LeftBrow", "RightBrow",
    "LeftShoulder", "LeftElbow", "LeftWrist", "LeftFingers",
    "RightShoulder", "RightElbow", "RightWrist", "RightFingers",
    "LeftHip", "LeftKnee", "LeftAnkle", "RightHip", "RightKnee", "RightAnkle",
    "Mouth", "HairCap",
  ].filter((n) => !world.has(n));
  console.log(`  rig complete         ${missing.length === 0 ? "yes" : `MISSING ${missing.join(", ")}`}`);
  const mouthMesh = world.get("Mouth")?.node?.mesh;
  console.log(`  mouth morph targets  ${json.meshes[mouthMesh]?.primitives?.[0]?.targets?.length ?? 0}`);

  // The body mesh writes depth, so any feature tucked behind the skull surface is
  // invisible. Compare each feature's frontmost point against the real skull
  // vertices around it rather than trusting the authored offsets.
  const bodyVerts = readVec3(json, bin, json.meshes[bodyNode.mesh].primitives[0].attributes.POSITION);
  const bodyZAt = (fx, fy, headOnly) => {
    let best = -Infinity;
    for (let i = 0; i < bodyVerts.length; i += 3) {
      const x = bodyVerts[i];
      const y = bodyVerts[i + 1];
      if (headOnly && y < canon.chinY) continue;
      if (!headOnly && y > canon.chinY) continue;
      if (Math.abs(x - fx) > 0.06 || Math.abs(y - fy) > 0.06) continue;
      best = Math.max(best, bodyVerts[i + 2]);
    }
    return best;
  };
  const skullZAt = (fx, fy) => bodyZAt(fx, fy, true);

  console.log("  feature depth vs body surface:");
  // Feature matrices are translate+scale (brow rotation is about z), so a
  // subtree's frontmost point is its local max z scaled and offset.
  const frontOf = (entry) => {
    let front = -Infinity;
    const visit = (node, matrix) => {
      if (node.mesh !== undefined) {
        const localMax = json.accessors[json.meshes[node.mesh].primitives[0].attributes.POSITION].max;
        front = Math.max(front, matrix[14] + localMax[2] * matrix[10]);
      }
      for (const child of node.children || []) {
        const childNode = nodes[child];
        visit(childNode, multiply(matrix, localMatrix(childNode)));
      }
    };
    visit(entry.node, entry.matrix);
    return front;
  };

  const checks = [
    ["LeftEyeMesh", true], ["LeftBrowMesh", true], ["Nose", true],
    ["Mouth", true], ["RightEyeMesh", true], ["SalareenMark", false],
  ];
  for (const [name, headOnly] of checks) {
    const entry = world.get(name);
    if (!entry) continue;
    const front = frontOf(entry);
    const surface = bodyZAt(entry.matrix[12], entry.matrix[13], headOnly);
    const gap = front - surface;
    const verdict = gap > 0.004 ? `proud +${gap.toFixed(4)}` : `BURIED ${gap.toFixed(4)}`;
    if (gap <= 0.004) failures += 1;
    console.log(`    ${name.padEnd(13)} front=${front.toFixed(4)} body=${surface.toFixed(4)}  ${verdict}`);
  }

  if (Math.abs(min[1]) > 0.005) {
    console.log(`    WARNING feet float ${min[1].toFixed(4)} above the floor`);
    failures += 1;
  }
}

if (failures > 0) {
  console.error(`\n${failures} proportion check(s) failed.`);
  process.exit(1);
}
console.log("\nAll proportion checks passed.");

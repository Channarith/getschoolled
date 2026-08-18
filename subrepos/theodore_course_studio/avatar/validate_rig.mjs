/**
 * Offline validator for a presenter GLB. Confirms an imported (artist- or
 * Meshy-generated) model carries the bones and blendshapes our teach runtime
 * needs, checked two ways:
 *   1. V2 spec coverage against avatar_rig_config_v2.json (exact names).
 *   2. Runtime drivability against the alias layer in avatar_rig.js — i.e. will
 *      our cues actually move it, whichever naming convention it uses.
 *
 * Usage:
 *   node validate_rig.mjs [path/to/model.glb]
 * Default target: ../src/theodore_course_studio/avatar_static/presenter_female.glb
 *
 * Exits non-zero if the core skeleton or the mouth cannot be driven.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { BONE_ALIASES, FACE_ALIASES, VISEME_TO_V2 } from "./avatar_rig.js";

const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, "..", "src", "theodore_course_studio", "avatar_static");
const target = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(dist, "presenter_female.glb");

function readGlbJson(file) {
  const buf = fs.readFileSync(file);
  const jsonLength = buf.readUInt32LE(12);
  return JSON.parse(buf.slice(20, 20 + jsonLength).toString("utf8"));
}

const config = JSON.parse(
  fs.readFileSync(path.join(root, "avatar_rig_config_v2.json"), "utf8"),
);

if (!fs.existsSync(target)) {
  console.error(`✗ GLB not found: ${target}`);
  process.exit(2);
}

const json = readGlbJson(target);

// --- collect bone + blendshape names from the GLB -------------------------
const boneNames = new Set((json.nodes || []).map((n) => n.name).filter(Boolean));
const morphNames = new Set();
for (const mesh of json.meshes || []) {
  for (const nm of mesh.extras?.targetNames || []) morphNames.add(nm);
  for (const prim of mesh.primitives || []) {
    for (const nm of prim.extras?.targetNames || []) morphNames.add(nm);
  }
}
const lc = (s) => String(s || "").toLowerCase();
const boneLc = new Set([...boneNames].map(lc));
const morphLc = new Set([...morphNames].map(lc));
const hasBone = (name) => boneLc.has(lc(name));
const hasMorph = (name) => morphLc.has(lc(name));
const anyPresent = (cands, has) => cands.some((c) => has(c));

console.log(`Validating ${path.relative(process.cwd(), target)}`);
console.log(`  bones: ${boneNames.size}   blendshapes: ${morphNames.size}\n`);

// --- 1. V2 spec coverage ---------------------------------------------------
console.log("V2 spec coverage (avatar_rig_config_v2.json):");
const reportGroup = (label, names, has) => {
  const present = names.filter((n) => has(n));
  const missing = names.filter((n) => !has(n));
  const pct = names.length ? Math.round((present.length / names.length) * 100) : 100;
  console.log(`  ${label}: ${present.length}/${names.length} (${pct}%)`);
  if (missing.length) console.log(`      missing: ${missing.join(", ")}`);
};
for (const [group, names] of Object.entries(config.required_bones_skeleton)) {
  reportGroup(`bones.${group}`, names, hasBone);
}
for (const [group, names] of Object.entries(config.required_blendshapes)) {
  reportGroup(`morphs.${group}`, names, hasMorph);
}

// --- 2. Runtime drivability (alias-aware) ---------------------------------
console.log("\nRuntime drivability (alias-aware):");
const CORE = [
  "Hips", "Spine", "Chest", "Neck", "Head",
  "LeftShoulder", "RightShoulder", "LeftElbow", "RightElbow",
  "LeftWrist", "RightWrist",
];
const failures = [];
const driveReport = (logical, cands) => {
  const ok = anyPresent(cands, hasBone);
  if (!ok && CORE.includes(logical)) failures.push(`bone:${logical}`);
  return ok;
};
const drivable = [];
const notDrivable = [];
for (const [logical, cands] of Object.entries(BONE_ALIASES)) {
  (driveReport(logical, cands) ? drivable : notDrivable).push(logical);
}
console.log(`  joints drivable: ${drivable.length}/${Object.keys(BONE_ALIASES).length}`);
if (notDrivable.length) console.log(`      not found: ${notDrivable.join(", ")}`);

const mouthOk = anyPresent(FACE_ALIASES.mouthOpen, hasMorph);
const visemeCount = Object.values(VISEME_TO_V2).filter((m) => hasMorph(m)).length;
const blinkOk = anyPresent(FACE_ALIASES.blinkL, hasMorph) || anyPresent(FACE_ALIASES.blinkR, hasMorph);
const smileOk = anyPresent(FACE_ALIASES.smile, hasMorph);
console.log(`  mouth: ${mouthOk ? "yes" : "NO"}   visemes: ${visemeCount}/${Object.keys(VISEME_TO_V2).length}   blink: ${blinkOk ? "yes" : "no"}   smile: ${smileOk ? "yes" : "no"}`);
if (!mouthOk) failures.push("face:mouth");

// --- verdict ---------------------------------------------------------------
console.log("");
if (failures.length) {
  console.error(`✗ FAIL — cannot drive: ${failures.join(", ")}`);
  process.exit(1);
}
console.log("✓ PASS — core skeleton and mouth are drivable by the teach runtime.");
if (visemeCount === 0) console.log("  note: no ARKit visemes found; lip-sync will use the jaw/mouth fallback.");
if (!blinkOk) console.log("  note: no eyelid blendshapes; blink will use eye-scale fallback.");

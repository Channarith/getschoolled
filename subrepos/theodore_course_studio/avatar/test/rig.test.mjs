/**
 * Unit tests for the rig adapter. Builds synthetic scene graphs (no GLB needed)
 * for both the Serenity V2 rig and our procedural rig, and asserts the adapter
 * resolves bones and drives the face for each. This proves the import path works
 * before any artist/Meshy GLB exists.
 *
 * Run: node --test   (from the avatar/ dir)
 */
import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { resolveSkeleton, createFaceDriver } from "../avatar_rig.js";

function boneGroup(names) {
  const group = new THREE.Group();
  for (const name of names) {
    const bone = new THREE.Bone();
    bone.name = name;
    group.add(bone);
  }
  return group;
}

function faceMesh(dict) {
  const mesh = new THREE.Mesh(new THREE.BufferGeometry());
  mesh.name = "Face";
  mesh.morphTargetDictionary = dict;
  mesh.morphTargetInfluences = new Array(Object.keys(dict).length).fill(0);
  return mesh;
}

test("resolveSkeleton maps a Serenity V2 rig into logical joints", () => {
  const root = boneGroup([
    "Hips", "Spine", "Chest", "Neck", "Head", "Jaw",
    "UpperArm_L", "LowerArm_L", "Hand_L",
    "UpperArm_R", "LowerArm_R", "Hand_R",
    "UpperLeg_L", "LowerLeg_L", "Foot_L",
    "UpperLeg_R", "LowerLeg_R", "Foot_R",
    "Eye_L", "Eye_R", "Index_Proximal_L", "Index_Proximal_R",
  ]);
  const { nodes, rig, missing } = resolveSkeleton(root);
  assert.equal(rig, "v2");
  assert.equal(nodes.LeftShoulder.name, "UpperArm_L");
  assert.equal(nodes.RightElbow.name, "LowerArm_R");
  assert.equal(nodes.LeftWrist.name, "Hand_L");
  assert.equal(nodes.Head.name, "Head");
  assert.equal(nodes.LeftEye.name, "Eye_L");
  assert.equal(nodes.LeftFingers.name, "Index_Proximal_L");
  assert.equal(nodes.LeftHip.name, "UpperLeg_L");
  // Crown/Brow/Ear are procedural-only; fine that they're missing on V2.
  assert.ok(missing.includes("Crown"));
});

test("resolveSkeleton keeps our procedural rig identical", () => {
  const root = boneGroup([
    "Hips", "Spine", "Chest", "Neck", "Head", "Jaw",
    "LeftShoulder", "RightShoulder", "LeftElbow", "RightElbow",
    "LeftWrist", "RightWrist", "LeftFingers", "RightFingers",
    "LeftEye", "RightEye", "Crown",
  ]);
  const { nodes, rig } = resolveSkeleton(root);
  assert.equal(rig, "procedural");
  assert.equal(nodes.LeftShoulder.name, "LeftShoulder");
  assert.equal(nodes.Crown.name, "Crown");
});

test("face driver drives V2 visemes + eyelid blink", () => {
  const root = new THREE.Group();
  const mesh = faceMesh({
    viseme_sil: 0, viseme_PP: 1, viseme_aa: 2, viseme_E: 3, viseme_O: 4, viseme_U: 5,
    eyeBlink_L: 6, eyeBlink_R: 7, smile: 8, eyebrow_raise: 9, jawOpen: 10,
  });
  root.add(mesh);
  const face = createFaceDriver(root);
  assert.equal(face.mode, "v2");
  assert.equal(face.hasVisemes, true);
  assert.equal(face.hasBlink, true);

  face.beginFrame();
  face.setViseme("aa", 1);
  face.update(1);
  assert.ok(mesh.morphTargetInfluences[2] > 0.6, "viseme_aa should open");
  assert.ok(mesh.morphTargetInfluences[3] < 0.1, "viseme_E should stay closed");

  face.beginFrame();
  face.setBlink(1);
  face.update(1);
  assert.ok(mesh.morphTargetInfluences[6] > 0.6, "left eyelid should close");
  assert.ok(mesh.morphTargetInfluences[7] > 0.6, "right eyelid should close");
});

test("face driver falls back to procedural mouth morphs", () => {
  const root = new THREE.Group();
  const mesh = faceMesh({ mouthOpen: 0, mouthWide: 1, mouthSmile: 2 });
  root.add(mesh);
  const face = createFaceDriver(root);
  assert.equal(face.mode, "procedural");
  assert.equal(face.hasVisemes, false);
  assert.equal(face.hasBlink, false);

  face.beginFrame();
  face.setMouth(0.8, 0.2);
  face.setExpression(0.05, 0.5);
  face.update(1);
  assert.ok(mesh.morphTargetInfluences[0] > 0.6, "mouthOpen should track");
  assert.ok(mesh.morphTargetInfluences[2] > 0.3, "smile should track");

  // A frame without setMouth relaxes the transient mouth channel back toward 0.
  face.beginFrame();
  face.setExpression(0.05, 0.5);
  face.update(1);
  assert.ok(mesh.morphTargetInfluences[0] < 0.2, "mouthOpen relaxes when idle");
  assert.ok(mesh.morphTargetInfluences[2] > 0.3, "smile persists when idle");
});

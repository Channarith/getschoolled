import test from "node:test";
import assert from "node:assert/strict";

import {
  poseForAge,
  sceneForMode,
  tierForAge,
} from "../../app/lib/mascotPose.ts";

test("tierForAge classifies the four age tiers at their boundaries", () => {
  assert.equal(tierForAge(3), "child");
  assert.equal(tierForAge(12), "child");
  assert.equal(tierForAge(13), "teen");
  assert.equal(tierForAge(19), "teen");
  assert.equal(tierForAge(20), "adult");
  assert.equal(tierForAge(59), "adult");
  assert.equal(tierForAge(60), "senior");
  assert.equal(tierForAge(120), "senior");
});

test("tierForAge falls back to adult for non-finite ages", () => {
  assert.equal(tierForAge(Number.NaN), "adult");
  assert.equal(tierForAge(Number.POSITIVE_INFINITY), "adult");
});

test("poseForAge picks a visibly smaller scale for children than for adults", () => {
  assert.ok(poseForAge(7).scale < poseForAge(40).scale);
  assert.ok(poseForAge(7).scale < poseForAge(16).scale);
});

test("poseForAge gives seniors a glasses accessory and children a child silhouette", () => {
  assert.equal(poseForAge(72).accessory, "👓");
  assert.equal(poseForAge(8).accessory, "🧒");
  assert.equal(poseForAge(15).accessory, "🎒");
  assert.equal(poseForAge(40).accessory, "");
});

test("sceneForMode maps every onboarding learning mode to its own scene kind", () => {
  assert.equal(sceneForMode("video").kind, "video");
  assert.equal(sceneForMode("live_teacher").kind, "teacher");
  assert.equal(sceneForMode("presentation").kind, "presentation");
  assert.equal(sceneForMode("reading").kind, "reading");
  assert.equal(sceneForMode("tutoring").kind, "tutoring");
  assert.equal(sceneForMode("gaming").kind, "gaming");
});

test("sceneForMode falls back to idle for unknown modes", () => {
  assert.equal(sceneForMode("not-a-mode").kind, "idle");
  assert.equal(sceneForMode("").kind, "idle");
});

import test from "node:test";
import assert from "node:assert/strict";
import {
  EXPRESSION_LABELS,
  EXPRESSION_NAMES,
  expressionForSceneKind,
} from "../../app/components/mascot3d/faceTexture.ts";

test("exactly eight distinct facial expressions ship", () => {
  // The user explicitly requested these eight (cute, serious, angry, sad,
  // crying, excited, curious, mischievous). Pin the count so a future
  // refactor cannot silently drop one.
  assert.equal(EXPRESSION_NAMES.length, 8);
  assert.equal(new Set(EXPRESSION_NAMES).size, 8);
  for (const required of [
    "cute",
    "serious",
    "angry",
    "sad",
    "crying",
    "excited",
    "curious",
    "mischievous",
  ]) {
    assert.ok(EXPRESSION_NAMES.includes(required), `missing expression: ${required}`);
  }
});

test("every expression has a human-readable label for the lab UI picker", () => {
  for (const name of EXPRESSION_NAMES) {
    const label = EXPRESSION_LABELS[name];
    assert.ok(label, `missing label for ${name}`);
    assert.ok(label.length > 4, `label for ${name} is too short: ${label}`);
  }
});

test("every MascotScene kind maps to a valid expression", () => {
  // Keep this list in sync with MascotScene["kind"] in app/lib/mascotPose.ts.
  const sceneKinds = [
    "idle",
    "flyin-point",
    "dance",
    "age-morph",
    "video",
    "teacher",
    "presentation",
    "reading",
    "tutoring",
    "gaming",
  ];
  for (const kind of sceneKinds) {
    const expr = expressionForSceneKind(kind);
    assert.ok(EXPRESSION_NAMES.includes(expr), `${kind} -> ${expr} is not a valid expression`);
  }
});

test("unknown scene kind falls back to the default cute expression", () => {
  assert.equal(expressionForSceneKind(undefined), "cute");
  assert.equal(expressionForSceneKind("totally-made-up-scene"), "cute");
});

test("teacher and presentation default to serious (classroom mode)", () => {
  assert.equal(expressionForSceneKind("teacher"), "serious");
  assert.equal(expressionForSceneKind("presentation"), "serious");
});

test("flyin-point and dance default to excited (celebratory scenes)", () => {
  assert.equal(expressionForSceneKind("flyin-point"), "excited");
  assert.equal(expressionForSceneKind("dance"), "excited");
});

test("gaming defaults to mischievous and reading to curious", () => {
  assert.equal(expressionForSceneKind("gaming"), "mischievous");
  assert.equal(expressionForSceneKind("reading"), "curious");
});

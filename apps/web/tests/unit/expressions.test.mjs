import test from "node:test";
import assert from "node:assert/strict";
import {
  EXPRESSION_LABELS,
  EXPRESSION_NAMES,
  MOOD_PROFILES,
  expressionForSceneKind,
} from "../../app/components/mascot3d/expressions.ts";

test("exactly eight distinct mascot expressions ship", () => {
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
    assert.ok(EXPRESSION_NAMES.includes(required), `missing: ${required}`);
  }
});

test("every expression has a label and a mood profile", () => {
  for (const name of EXPRESSION_NAMES) {
    assert.ok(EXPRESSION_LABELS[name], `missing label for ${name}`);
    assert.ok(MOOD_PROFILES[name], `missing mood profile for ${name}`);
    const mood = MOOD_PROFILES[name];
    assert.equal(mood.emissive.length, 3, `${name} emissive must be [r,g,b]`);
    for (const v of mood.emissive) {
      assert.ok(v >= 0 && v <= 1, `${name} emissive channel out of range: ${v}`);
    }
    assert.ok(mood.emissiveIntensity >= 0, `${name} intensity must be >= 0`);
    assert.ok(
      ["none", "tears", "sparkles", "shimmer"].includes(mood.particles),
      `${name} particles kind unknown: ${mood.particles}`,
    );
  }
});

test("mood postures match the expression intent", () => {
  // The lab UI (and future consumers) rely on these physical cues to
  // make each expression visually distinct from the others.
  assert.ok(MOOD_PROFILES.sad.bodyLeanX > 0, "sad should hunch forward");
  assert.ok(MOOD_PROFILES.crying.bodyLeanX > 0, "crying should hunch forward");
  assert.ok(MOOD_PROFILES.curious.bodyTiltZ > 0, "curious should tilt right");
  assert.ok(
    MOOD_PROFILES.mischievous.bodyTiltZ < 0,
    "mischievous should tilt left",
  );
  assert.equal(MOOD_PROFILES.crying.particles, "tears");
  assert.equal(MOOD_PROFILES.excited.particles, "sparkles");
  assert.equal(MOOD_PROFILES.angry.particles, "shimmer");
  // Pulse should fire on moods that benefit from a visible beat.
  assert.ok(MOOD_PROFILES.excited.pulseHz > 0, "excited should pulse");
  assert.ok(MOOD_PROFILES.angry.pulseHz > 0, "angry should pulse");
  assert.equal(MOOD_PROFILES.cute.pulseHz, 0, "cute default is calm");
});

test("every MascotScene kind maps to a valid expression", () => {
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
    assert.ok(
      EXPRESSION_NAMES.includes(expr),
      `${kind} -> ${expr} is not a valid expression`,
    );
  }
});

test("unknown scene kind falls back to the default cute expression", () => {
  assert.equal(expressionForSceneKind(undefined), "cute");
  assert.equal(expressionForSceneKind("totally-made-up-scene"), "cute");
});

// Executed by test_gesture_geometry_is_distance_invariant.
//
// Builds synthetic MediaPipe-shaped hands, then places the SAME pose at
// different scales (child near / far from the camera) and rotations to prove
// classification does not change. The old fixed-distance thresholds failed
// exactly this: a distant child read as a permanent fist.
import assert from "node:assert/strict";
import {
  FIST_MAX_PALMS, FINGERTIP_LANDMARKS, HAND_BONES, SIGNAL_HOLD_MS, AWAY_HOLD_MS, RETURN_HOLD_MS,
  MIRROR_HOLD_MS, MIRROR_PACES, MIRROR_ROUTINE, MIRROR_SEATED_MAX_Y,
  NINJA_DEFAULT_TECHNIQUE, NINJA_EFFECTS, NINJA_ELEMENTS, NINJA_FORMS, NINJA_HAND_SHAPES, NINJA_PLACEMENTS,
  NINJA_HOLD_GRACE_MS, NINJA_HOLD_MS, NINJA_RELEASE_MS, NINJA_SEALS, NINJA_TECHNIQUES, NINJA_TIER_LENGTHS,
  ninjaEffectParticles, ninjaEffectSpec, ninjaShapeFits, ninjaShapeOf, ninjaTechniqueList,
  activeFingertips, advanceMirrorBeat, advanceNinjaWeave, advanceThrowGesture, catchRadiusPx, claimTouch, coverFrame,
  createPresenceWatch, defaultMirrorPace, fingersPointed, freshMirrorRun,
  handShape, heartRatios, isHeartShape, localMathRound, mapMirroredLandmark, mirrorBeatMatched,
  mirrorPace, mirrorPose, mirrorStars, mirrorSummary, palmSpan, profileTouchAge,
  freshNinjaRun, newThrowTracker, ninjaSealFits, ninjaTechnique, projectThrowTarget, recognizeNinjaSeal,
  syntheticHand, tipHitsTarget, traceProgress,
} from "../src/theodore_children_webcam_lab/static/vision_math.js";

// A canonical right hand, palm size 1.0, fingers pointing up (-y).
// Index order matches MediaPipe: 0 wrist, 1-4 thumb, 5-8 index, 9-12 middle,
// 13-16 ring, 17-20 pinky.
function canonicalHand({ curl = 0 } = {}) {
  const reach = (base, len) => base + len * (1 - curl);
  const finger = (x, mcpY, pipLen, tipLen) => [
    { x, y: mcpY },
    { x, y: -reach(-mcpY, pipLen) * -1 },
    { x, y: mcpY - pipLen * (1 - curl) },
    { x, y: mcpY - (pipLen + tipLen) * (1 - curl) },
  ];
  const pts = [{ x: 0, y: 0 }];
  // Thumb splays sideways rather than up.
  pts.push(
    { x: 0.25, y: -0.15 },
    { x: 0.45, y: -0.3 },
    { x: 0.6 - 0.15 * curl, y: -0.42 + 0.1 * curl },
    { x: 0.72 - 0.35 * curl, y: -0.52 + 0.28 * curl },
  );
  for (const [x, pip, tip] of [
    [-0.12, 0.55, 0.4],
    [0.0, 0.6, 0.45],
    [0.12, 0.55, 0.4],
    [0.24, 0.45, 0.32],
  ]) {
    pts.push(...finger(x, -1.0, pip, tip));
  }
  return pts;
}

// Place a hand in the frame: scale (camera distance), rotate, translate.
function place(points, { scale, angle = 0, at = { x: 0.5, y: 0.5 } }) {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return points.map((p) => {
    const x = p.x * scale;
    const y = p.y * scale;
    return { x: at.x + x * cos - y * sin, y: at.y + x * sin + y * cos };
  });
}

// --- 1. An open hand stays open, and a fist stays a fist, at any distance ----
// 0.055 ~ a child across the room; 0.22 ~ hand near the lens.
const distances = [0.055, 0.09, 0.14, 0.22];

for (const scale of distances) {
  const open = handShape(place(canonicalHand({ curl: 0 }), { scale }));
  assert.equal(open.fist, false, `open hand read as a fist at scale ${scale}`);
  assert.ok(
    open.tipPalms > FIST_MAX_PALMS,
    `open hand tipPalms ${open.tipPalms.toFixed(2)} should exceed ${FIST_MAX_PALMS} at scale ${scale}`,
  );

  const closed = handShape(place(canonicalHand({ curl: 0.95 }), { scale }));
  assert.equal(closed.fist, true, `fist missed at scale ${scale}`);
}

// The palm ruler must track the scale it was given, which is what makes the
// ratios above comparable across distances.
const spans = distances.map((scale) =>
  palmSpan(place(canonicalHand(), { scale })),
);
for (let i = 1; i < spans.length; i++) {
  assert.ok(spans[i] > spans[i - 1], "palm span should grow as the hand nears");
}
// Ratio of measured span to requested scale is constant => a true unit.
const unit = spans.map((s, i) => s / distances[i]);
for (const u of unit) {
  assert.ok(
    Math.abs(u - unit[0]) < 1e-9,
    `palm span is not proportional to scale: ${unit.join(", ")}`,
  );
}

// --- 2. Rotation must not turn extended fingers into curled ones -------------
for (const angle of [0, Math.PI / 6, Math.PI / 3, Math.PI / 2, Math.PI]) {
  const open = handShape(place(canonicalHand({ curl: 0 }), { scale: 0.12, angle }));
  assert.equal(
    open.fist,
    false,
    `open hand read as a fist when rotated ${Math.round((angle * 180) / Math.PI)}deg`,
  );
  assert.ok(
    open.count >= 4,
    `expected >=4 fingers at ${Math.round((angle * 180) / Math.PI)}deg, got ${open.count}`,
  );
}

// --- 3. A heart is a cleft and a point, not a circle, at any distance --------
function blankHand() {
  return Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5 }));
}
function heartPose(scale) {
  // Index knuckles are the two high lobes. Fingertips meet lower, in the dip.
  // Thumbs meet at the bottom point. Wrists stay apart.
  const s = scale;
  const left = blankHand();
  left[0] = { x: 0.5 - 2.0 * s, y: 0.55 + 1.2 * s };
  left[9] = { x: 0.5 - 1.4 * s, y: 0.55 };
  left[5] = { x: 0.5 - 1.05 * s, y: 0.55 - 1.35 * s };
  left[8] = { x: 0.5 - 0.12 * s, y: 0.55 - 0.55 * s };
  left[4] = { x: 0.5 - 0.15 * s, y: 0.55 + 1.55 * s };
  const right = blankHand();
  right[0] = { x: 0.5 + 2.0 * s, y: 0.55 + 1.2 * s };
  right[9] = { x: 0.5 + 1.4 * s, y: 0.55 };
  right[5] = { x: 0.5 + 1.05 * s, y: 0.55 - 1.35 * s };
  right[8] = { x: 0.5 + 0.12 * s, y: 0.55 - 0.55 * s };
  right[4] = { x: 0.5 + 0.15 * s, y: 0.55 + 1.55 * s };
  return [left, right];
}
function circlePose(scale) {
  // Fingertips are the top of a ring, so there is no cleft between lobes.
  const s = scale;
  const left = blankHand();
  left[0] = { x: 0.5 - 2.2 * s, y: 0.55 };
  left[9] = { x: 0.5 - 1.5 * s, y: 0.55 };
  left[5] = { x: 0.5 - 1.2 * s, y: 0.55 - 0.2 * s };
  left[8] = { x: 0.5 - 0.15 * s, y: 0.55 - 1.3 * s };
  left[4] = { x: 0.5 - 0.15 * s, y: 0.55 + 1.3 * s };
  const right = blankHand();
  right[0] = { x: 0.5 + 2.2 * s, y: 0.55 };
  right[9] = { x: 0.5 + 1.5 * s, y: 0.55 };
  right[5] = { x: 0.5 + 1.2 * s, y: 0.55 - 0.2 * s };
  right[8] = { x: 0.5 + 0.15 * s, y: 0.55 - 1.3 * s };
  right[4] = { x: 0.5 + 0.15 * s, y: 0.55 + 1.3 * s };
  return [left, right];
}

for (const scale of [0.06, 0.1, 0.16]) {
  const [a, b] = heartPose(scale);
  const ratios = heartRatios(a, b, (palmSpan(a) + palmSpan(b)) / 2);
  assert.ok(ratios, "heart ratios should be computable");
  // Ratios must be scale-free: the same pose gives the same numbers.
  const reference = heartRatios(
    ...heartPose(0.1),
    (palmSpan(heartPose(0.1)[0]) + palmSpan(heartPose(0.1)[1])) / 2,
  );
  for (const key of ["tips", "thumbs", "wrists", "cleft", "point", "lobes"]) {
    assert.ok(
      Math.abs(ratios[key] - reference[key]) < 1e-6,
      `heart ${key} changed with camera distance: ${ratios[key]} vs ${reference[key]}`,
    );
  }
  assert.equal(isHeartShape(ratios), true, `heart pose missed at scale ${scale}`);
}

{
  const [a, b] = circlePose(0.1);
  const ratios = heartRatios(a, b, (palmSpan(a) + palmSpan(b)) / 2);
  assert.equal(
    isHeartShape(ratios), false,
    "a circle made with the hands is not a heart",
  );
}

// Two hands clamped together (wrists touching) must NOT count as a heart, or
// any two-handed clump would pass the round.
{
  const clump = [
    place(canonicalHand({ curl: 0.9 }), { scale: 0.1, at: { x: 0.5, y: 0.5 } }),
    place(canonicalHand({ curl: 0.9 }), { scale: 0.1, at: { x: 0.505, y: 0.5 } }),
  ];
  const ratios = heartRatios(
    clump[0], clump[1], (palmSpan(clump[0]) + palmSpan(clump[1])) / 2,
  );
  assert.equal(
    isHeartShape(ratios), false,
    "wrists together should not be accepted as a heart",
  );
}

// A single hand cannot make a two-handed heart.
assert.equal(heartRatios(canonicalHand(), null, 1), null);
assert.equal(isHeartShape(null), false);

const demoFist = handShape(syntheticHand({ x: 0.4, y: 0.4 }, { pose: "fist" }));
assert.equal(demoFist.fist, true, "demo fist pose must classify as a fist");
const demoIndex = handShape(syntheticHand({ x: 0.4, y: 0.4 }, { pose: "index" }));
assert.equal(demoIndex.indexUp, true, "demo index pose must raise only the index");
assert.equal(demoIndex.fist, false);
assert.equal(fingersPointed(demoIndex), true, "a pointed finger can color");
assert.equal(fingersPointed(demoFist), false, "a fist lifts the marker");
assert.equal(fingersPointed(handShape(syntheticHand({ x: 0.4, y: 0.4 }, { pose: "open" }))), true);
assert.ok(activeFingertips(syntheticHand({ x: 0.4, y: 0.4 }, { pose: "index" }), "7-10").includes(8));
assert.deepEqual(activeFingertips(syntheticHand({ x: 0.4, y: 0.4 }, { pose: "fist" }), "4-6"), []);

// Palm span is 1. A closed fist keeps every tip near the wrist. A single
// raised finger must still be a touch even when that makes the hand a fist.
function placedHand(tips) {
  const wrist = { x: 0.5, y: 0.8 };
  const pts = Array.from({ length: 21 }, () => ({ x: wrist.x, y: wrist.y }));
  pts[0] = wrist;
  pts[9] = { x: 0.5, y: 0.7 };
  for (const [tip, pip, tipPalms, pipPalms] of tips) {
    pts[pip] = { x: 0.5, y: wrist.y - 0.1 * pipPalms };
    pts[tip] = { x: 0.5, y: wrist.y - 0.1 * tipPalms };
  }
  return pts;
}
{
  const buried = placedHand([[8, 6, 0.9, 0.7], [12, 10, 0.9, 0.7], [16, 14, 0.9, 0.7], [20, 18, 0.85, 0.7], [4, 2, 0.8, 0.6]]);
  const shape = handShape(buried);
  assert.equal(shape.fist, true);
  assert.equal(fingersPointed(shape), false);
  assert.deepEqual(activeFingertips(buried, "4-6"), [], "a palm is not a touch for young hands");
  assert.deepEqual(activeFingertips(buried, "7-10"), [], "a palm is not a touch for older hands");
}
{
  const point = placedHand([[8, 6, 1.3, 1.22], [12, 10, 0.95, 0.7], [16, 14, 0.9, 0.7], [20, 18, 0.9, 0.7], [4, 2, 0.9, 0.7]]);
  const shape = handShape(point);
  assert.equal(shape.fist, true, "a short point on closed fingers is still a fist");
  assert.equal(fingersPointed(shape), false, "the open-hand gate would miss this point");
  assert.deepEqual(activeFingertips(point, "4-6"), [8], "young hands accept the short point");
  assert.deepEqual(activeFingertips(point, "7-10"), [], "older hands need a clearer point");
  assert.ok(catchRadiusPx(500, "4-6") > catchRadiusPx(500, "7-10"));
  assert.ok(catchRadiusPx(500, "child") > catchRadiusPx(500, "teen"));
}
{
  const thumb = placedHand([[8, 6, 0.95, 0.7], [12, 10, 0.95, 0.7], [16, 14, 0.9, 0.7], [20, 18, 0.9, 0.7], [4, 2, 2.2, 1.0]]);
  assert.equal(handShape(thumb).fist, true);
  assert.equal(fingersPointed(handShape(thumb)), false);
  assert.deepEqual(activeFingertips(thumb, "7-10"), [4], "a thumb on a fist still touches");
  assert.deepEqual(FINGERTIP_LANDMARKS, [4, 8, 12, 16, 20]);
}
assert.equal(tipHitsTarget([{ x: 10, y: 10 }, { x: 90, y: 40 }], { x: 12, y: 11 }, 5), true);
assert.equal(tipHitsTarget([{ x: 10, y: 10 }], { x: 40, y: 40 }, 5), false);
assert.equal(profileTouchAge({ query: "5" }), "4-6");
assert.equal(profileTouchAge({ ageYears: "9", ageBand: "child" }), "7-10");
assert.equal(profileTouchAge({ ageBand: "child" }), "4-6");
assert.equal(profileTouchAge({ ageBand: "teen" }), "7-10");
{
  const first = claimTouch(null, "balloon", 1000, 420);
  assert.equal(first.claimed, true);
  const repeat = claimTouch(first.latch, "balloon", 1200, 420);
  assert.equal(repeat.claimed, false);
  const later = claimTouch(repeat.latch, "balloon", 1500, 420);
  assert.equal(later.claimed, true);
  const other = claimTouch(first.latch, "fish", 1100, 420);
  assert.equal(other.claimed, true);
}

// Math Toss requires a held fist, a palm-relative pull-back, and a fast
// opposite-direction opening. A short accidental close/open cannot launch.
{
  let tracker = newThrowTracker();
  let step = advanceThrowGesture(tracker, {at: 100, palm: 50, fist: true, point: {x: 120, y: 220}}, "7-10");
  tracker = step.tracker;
  assert.equal(step.event, null);
  step = advanceThrowGesture(tracker, {at: 260, palm: 50, fist: true, point: {x: 120, y: 220}}, "7-10");
  tracker = step.tracker;
  assert.equal(step.event, "grabbed");
  step = advanceThrowGesture(tracker, {at: 340, palm: 50, fist: true, point: {x: 70, y: 220}}, "7-10");
  tracker = step.tracker;
  assert.equal(step.event, "cocked");
  step = advanceThrowGesture(tracker, {at: 390, palm: 50, fist: true, point: {x: 76, y: 220}}, "7-10");
  tracker = step.tracker;
  step = advanceThrowGesture(tracker, {at: 450, palm: 50, fist: false, point: {x: 150, y: 220}}, "7-10");
  assert.equal(step.event, "released");
  assert.ok(step.release.speed > 2.8);
  assert.ok(step.release.reversal < 0);

  const hit = projectThrowTarget(step.release.origin, step.release.velocity, [
    {id: "wrong", x: 300, y: 90, radius: 45},
    {id: "correct", x: 320, y: 220, radius: 60},
  ]);
  assert.equal(hit.id, "correct");
}
{
  let step = advanceThrowGesture(newThrowTracker(), {at: 0, palm: 50, fist: true, point: {x: 100, y: 100}}, "4-6");
  step = advanceThrowGesture(step.tracker, {at: 40, palm: 50, fist: false, point: {x: 106, y: 100}}, "4-6");
  assert.equal(step.event, null);
  assert.equal(step.tracker.phase, "ready");
  assert.equal(projectThrowTarget({x: 0, y: 0}, {x: 1, y: 0}, [{id: "behind", x: -10, y: 0}], 5), null);
}

// A wide stage crops a square camera. The skeleton has to land on the visible
// picture, not on the full stage rectangle.
const cropped = coverFrame(1000, 500, 1000, 1000);
assert.equal(cropped.x, 0);
assert.equal(cropped.y, -250);
assert.equal(cropped.w, 1000);
assert.equal(cropped.h, 1000);
const mid = mapMirroredLandmark({ x: 0.5, y: 0.5 }, cropped);
assert.equal(mid.x, 500);
assert.equal(mid.y, 250);
const demo = coverFrame(800, 600, 0, 0);
assert.equal(demo.w, 800);
assert.equal(demo.h, 600);
assert.ok(HAND_BONES.some((pair) => pair[0] === 0 && pair[1] === 5));

function stroke(from, to, steps) {
  const points = [];
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    points.push({ x: from[0] + (to[0] - from[0]) * t, y: from[1] + (to[1] - from[1]) * t });
  }
  return points;
}
const roughLetter = traceProgress(stroke([0.48, 0.28], [0.52, 0.72], 10), "7-10");
assert.equal(roughLetter.passed, true, "a single downstroke counts as a finished letter");
const tap = traceProgress([{ x: 0.5, y: 0.5 }, { x: 0.51, y: 0.51 }], "7-10");
assert.equal(tap.passed, false, "a tap is not a letter");
const offGuide = traceProgress(stroke([0.02, 0.02], [0.08, 0.9], 12), "4-6");
assert.equal(offGuide.passed, false, "a stroke outside the letter does not finish it");

const watch = createPresenceWatch();
const phoneFace = {
  facePresent: true,
  pitchDeg: 22,
  gazeDown: 0.6,
  yawDeg: 0,
  allowPoseOnly: true,
  source: "face_mesh",
};
assert.equal(watch.update({ ...phoneFace, atMs: 0 }).length, 0);
const noticed = watch.update({ ...phoneFace, atMs: SIGNAL_HOLD_MS });
assert.equal(noticed[0].kind, "looking_at_phone");
assert.equal(noticed[0].signal, "pitch_and_gaze");
assert.equal(watch.update({ facePresent: false, atMs: SIGNAL_HOLD_MS + 400, source: "face_mesh" }).length, 0);
const paused = watch.update({ facePresent: false, atMs: SIGNAL_HOLD_MS + 400 + AWAY_HOLD_MS, source: "face_mesh" });
assert.equal(paused[0].type, "pause");
const back = { ...phoneFace, pitchDeg: 2, gazeDown: 0 };
assert.equal(watch.update({ ...back, atMs: 8000 }).length, 0);
const resumed = watch.update({ ...back, atMs: 8000 + RETURN_HOLD_MS });
assert.equal(resumed[0].type, "resume");
assert.ok(resumed[0].awayMs >= AWAY_HOLD_MS);

const yunet = createPresenceWatch();
const turned = {
  facePresent: true,
  pitchDeg: 40,
  gazeDown: null,
  yawDeg: 0,
  allowPoseOnly: false,
  source: "yunet",
};
assert.equal(yunet.update({ ...turned, atMs: 0 }).length, 0);
assert.equal(yunet.update({ ...turned, atMs: SIGNAL_HOLD_MS }).length, 0, "five-point yaw-free face is not a phone");

// --- 4. The offline math round mirrors the server (shape invariants) --------
// game_engine.math_toss_round() is the source of truth. localMathRound() is
// the browser fallback used when /api/child/math-round is unreachable. The
// two must agree on operation, answer, and choices for every (age, index), or
// a lab restart could speak one prompt and score another.
for (const age of ["4-6", "7-10"]) {
  for (let i = 0; i < 12; i += 1) {
    const round = localMathRound(age, i);
    assert.equal(round.age_band, age, `offline round age mismatch at ${age}/${i}`);
    assert.equal(round.round_id, `math-toss-${age}-${i}`);
    assert.equal(round.index, i);
    assert.ok(round.choices.length === (age === "4-6" ? 2 : 3), `${age}/${i} choices length`);
    assert.equal(new Set(round.choices).size, round.choices.length, `${age}/${i} duplicate choice`);
    assert.ok(round.choices.includes(round.answer), `${age}/${i} answer not in choices`);
    for (const choice of round.choices) {
      assert.ok(Number.isInteger(choice) && choice >= 0, `${age}/${i} choice ${choice} invalid`);
    }
    assert.ok(round.answer >= 0, `${age}/${i} negative answer`);
    assert.equal(typeof round.question, "string");
    assert.equal(typeof round.speak, "string");
  }
}
// A string age ("child") should resolve the same way the server/UI do.
assert.equal(localMathRound("child", 0).age_band, "4-6");
assert.equal(localMathRound("teen", 0).age_band, "7-10");
assert.equal(localMathRound("", 0).age_band, "7-10", "default band is the server default");
// Negative or garbage index clamps to zero, not NaN.
assert.deepEqual(localMathRound("7-10", -5), localMathRound("7-10", 0));
assert.deepEqual(localMathRound("4-6", "nope"), localMathRound("4-6", 0));

// --- 5. Canceling a throw mid-gesture resets the state machine ---------------
// pointercancel / touchcancel / mode-switch must not leave the tracker in
// grabbed/cocked, or the next pose will replay a stale throw. The UI
// cancellation path is `tracker = newThrowTracker()`, so we assert the
// freshly-made tracker starts in `ready` with no residual grab/cock points
// or history. A regression here would let a canceled gesture replay as a
// phantom throw on the first new sample.
{
  // First build a tracker that advanced into cocked, to prove our preamble
  // puts the state machine somewhere a stale resume would be noticeable.
  let step = advanceThrowGesture(newThrowTracker(), {at: 100, palm: 50, fist: true, point: {x: 120, y: 220}}, "7-10");
  step = advanceThrowGesture(step.tracker, {at: 260, palm: 50, fist: true, point: {x: 120, y: 220}}, "7-10");
  step = advanceThrowGesture(step.tracker, {at: 340, palm: 50, fist: true, point: {x: 70, y: 220}}, "7-10");
  assert.equal(step.tracker.phase, "cocked", "preamble should reach cocked");

  // The cancel path.
  const fresh = newThrowTracker();
  assert.equal(fresh.phase, "ready");
  assert.equal(fresh.grabPoint, null);
  assert.equal(fresh.cockPoint, null);
  assert.deepEqual(fresh.history, []);
  // And one more sample on the fresh tracker must not emit a throw event, i.e.
  // no stored velocity could leak across the cancel boundary.
  const resumed = advanceThrowGesture(fresh, {at: 500, palm: 50, fist: false, point: {x: 80, y: 220}}, "7-10");
  assert.equal(resumed.event, null, "stale throw must not replay after cancel");
}

// --- 6. Mirror Hall: pace, seated lights, and a hold that scores -----------
assert.equal(MIRROR_ROUTINE.length, 8);
assert.equal(defaultMirrorPace("4-6"), "easy");
assert.equal(defaultMirrorPace("7-10"), "family");
assert.ok(MIRROR_PACES.easy.radius > MIRROR_PACES.family.radius);
assert.ok(MIRROR_PACES.family.radius > MIRROR_PACES.sharp.radius);
assert.equal(mirrorPace("easy").windowMs, 2200);
assert.equal(mirrorPace("family").windowMs, 1500);
assert.equal(mirrorPace("sharp").windowMs, 900);
assert.equal(mirrorPace("easy").retries, 1);
assert.equal(mirrorPace("sharp").retries, 0);
assert.equal(mirrorPace("nope").id, "family");

const standingFreeze = mirrorPose(7, { seated: false });
const seatedFreeze = mirrorPose(7, { seated: true });
assert.equal(standingFreeze.prompt, "Freeze");
assert.ok(standingFreeze.left.y > MIRROR_SEATED_MAX_Y);
assert.ok(standingFreeze.right.y > MIRROR_SEATED_MAX_Y);
assert.equal(seatedFreeze.left.y, MIRROR_SEATED_MAX_Y);
assert.equal(seatedFreeze.right.y, MIRROR_SEATED_MAX_Y);
assert.equal(seatedFreeze.head.y, standingFreeze.head.y);

function shiftPose(pose, dx) {
  const move = (point) => ({ x: point.x + dx, y: point.y });
  return { head: move(pose.head), left: move(pose.left), right: move(pose.right) };
}
const handsUp = mirrorPose(0);
const easyReach = mirrorPace("easy").radius;
assert.equal(mirrorBeatMatched(handsUp, handsUp, easyReach), true);
assert.equal(mirrorBeatMatched(shiftPose(handsUp, easyReach * 0.5), handsUp, easyReach), true);
assert.equal(mirrorBeatMatched(shiftPose(handsUp, easyReach + 0.02), handsUp, easyReach), false);
assert.equal(mirrorBeatMatched(
  { head: { x: 0, y: 1 }, left: { x: 0, y: 1 }, right: { x: 1, y: 1 } },
  handsUp,
  easyReach,
), false);

let hall = freshMirrorRun("family");
let clock = 0;
for (let beat = 0; beat < MIRROR_ROUTINE.length; beat += 1) {
  hall = { ...hall, windowStart: clock };
  const pose = mirrorPose(beat);
  assert.equal(mirrorBeatMatched(pose, pose, mirrorPace("family").radius), true);
  let step = advanceMirrorBeat(hall, { matched: true, now: clock });
  assert.equal(step.event, "hold", `beat ${beat} should start the hold`);
  clock += MIRROR_HOLD_MS;
  step = advanceMirrorBeat(step, { matched: true, now: clock });
  assert.equal(step.event, beat === MIRROR_ROUTINE.length - 1 ? "done" : "hit");
  hall = step;
  clock += 20;
}
assert.equal(hall.hits, 8);
assert.equal(hall.bestCombo, 8);
assert.equal(hall.finished, true);
assert.equal(mirrorStars(hall.hits, 8), 3);
assert.equal(mirrorSummary(hall).line, "8 of 8 lights. Best combo 8.");
assert.equal(mirrorStars(5, 8), 2);
assert.equal(mirrorStars(4, 8), 1);

let easyMiss = { ...freshMirrorRun("easy"), windowStart: 0 };
easyMiss = advanceMirrorBeat(easyMiss, { matched: false, now: 2200 });
assert.equal(easyMiss.event, "retry");
assert.equal(easyMiss.index, 0);
assert.equal(easyMiss.retries, 1);
easyMiss = advanceMirrorBeat(easyMiss, { matched: false, now: 4400 });
assert.equal(easyMiss.event, "miss");
assert.equal(easyMiss.index, 1);
assert.equal(easyMiss.combo, 0);

let sharpMiss = { ...freshMirrorRun("sharp"), windowStart: 0 };
sharpMiss = advanceMirrorBeat(sharpMiss, { matched: false, now: 900 });
assert.equal(sharpMiss.event, "miss");
assert.equal(sharpMiss.retries, 0);
assert.equal(sharpMiss.index, 1);

// --- 7. Ninja Weave: 75 signs, 220 finishers, release-gated sequences -------
const SHAPE_FINGERS = {
  fist: [false, false, false, false],
  point: [true, false, false, false],
  peace: [true, true, false, false],
  open: [true, true, true, true],
  horns: [true, false, false, true],
};
const ninjaHand = (x, shape, y = 300) => ({
  wrist: {x, y},
  fist: shape === "fist",
  fingers: SHAPE_FINGERS[shape],
});
const STAGE_W = 1000;
const STAGE_H = 800;
// Canonical pose for a sign: apart = 50% wide, together = 15%, stacked = 40% tall.
function poseFor(sealId) {
  const seal = NINJA_SEALS[sealId];
  if (seal.placement === "stacked") return [ninjaHand(500, seal.a, 160), ninjaHand(520, seal.b, 480)];
  const gap = seal.placement === "apart" ? 500 : 150;
  return [ninjaHand(250, seal.a), ninjaHand(250 + gap, seal.b)];
}

assert.ok(Object.keys(NINJA_SEALS).length >= 50, "at least 50 signs");
assert.equal(Object.keys(NINJA_SEALS).length,
  Object.keys(NINJA_HAND_SHAPES).length ** 2 * Object.keys(NINJA_PLACEMENTS).length);
assert.ok(Object.keys(NINJA_EFFECTS).length > 200, "over 200 finisher effects");
assert.equal(Object.keys(NINJA_EFFECTS).length, Object.keys(NINJA_ELEMENTS).length * NINJA_FORMS.length);
assert.equal(new Set(Object.values(NINJA_SEALS).map((seal) => seal.label)).size, Object.keys(NINJA_SEALS).length);
assert.equal(new Set(Object.values(NINJA_EFFECTS).map((fx) => fx.label)).size, Object.keys(NINJA_EFFECTS).length);

// Every sign reads back as itself from its canonical pose, and fits itself.
for (const sealId of Object.keys(NINJA_SEALS)) {
  const pose = poseFor(sealId);
  assert.equal(recognizeNinjaSeal(pose, STAGE_W, STAGE_H), sealId, `recognize ${sealId}`);
  assert.equal(ninjaSealFits(pose, sealId, STAGE_W, STAGE_H), true, `fits ${sealId}`);
  // Hand order in the input array does not matter.
  assert.equal(ninjaSealFits([...pose].reverse(), sealId, STAGE_W, STAGE_H), true);
}
assert.equal(recognizeNinjaSeal([ninjaHand(100, "open")], STAGE_W, STAGE_H), null);

// Real landmarks: a horns hand comes out of handShape as horns.
const curled = canonicalHand({ curl: 1 });
const hornsPoints = canonicalHand({ curl: 0 }).map((point, i) => (i >= 9 && i <= 16 ? curled[i] : point));
const hornsShape = handShape(place(hornsPoints, { scale: 0.12 }));
assert.deepEqual(hornsShape.fingers, [true, false, false, true]);
assert.equal(ninjaShapeOf(hornsShape), "horns");
assert.equal(ninjaShapeOf(handShape(place(canonicalHand({ curl: 0 }), { scale: 0.12 }))), "open");

// Room for error: a stray finger, three-of-four fingers, and in-between gaps.
assert.equal(ninjaShapeFits({fingers: [false, false, true, false]}, "fist"), true);
assert.equal(ninjaShapeFits({fingers: [true, false, false, true]}, "point"), true);
assert.equal(ninjaShapeFits({fingers: [true, true, true, false]}, "peace"), true);
assert.equal(ninjaShapeFits({fingers: [true, true, true, false]}, "open"), true);
assert.equal(ninjaShapeFits({fingers: [true, true, false, true]}, "horns"), true);
assert.equal(ninjaShapeFits({fingers: [true, true, true, true]}, "peace"), false);
assert.equal(ninjaShapeFits({fist: true, fingers: [true, true, true, true]}, "open"), false);
// Hands without per-finger flags (screen / demo) still work.
assert.equal(ninjaShapeOf({indexUp: true, count: 1}), "point");
assert.equal(ninjaShapeOf({count: 5}), "open");
const midGap = [ninjaHand(250, "open"), ninjaHand(550, "open")];
assert.equal(ninjaSealFits(midGap, "open-open-together", STAGE_W, STAGE_H), true);
assert.equal(ninjaSealFits(midGap, "open-open-apart", STAGE_W, STAGE_H), true);
assert.equal(ninjaSealFits(poseFor("open-open-apart"), "open-open-together", STAGE_W, STAGE_H), false);
assert.equal(ninjaSealFits(poseFor("open-open-together"), "open-open-apart", STAGE_W, STAGE_H), false);
assert.equal(ninjaSealFits(poseFor("open-open-apart"), "open-open-stacked", STAGE_W, STAGE_H), false);
// Order matters, except on Easy pace where swapped hands are accepted.
const swapped = poseFor("fist-open-apart");
assert.equal(ninjaSealFits(swapped, "open-fist-apart", STAGE_W, STAGE_H), false);
assert.equal(ninjaSealFits(swapped, "open-fist-apart", STAGE_W, STAGE_H, {mirrorOk: true}), true);

// Techniques: unique sequences, consecutive signs differ, every sign is used,
// lengths follow the form tier, early tiers stick to the easiest signs.
const sequenceKeys = new Set();
const usedSeals = new Set();
for (const technique of Object.values(NINJA_TECHNIQUES)) {
  assert.equal(technique.sequence.length, NINJA_TIER_LENGTHS[technique.tier]);
  assert.ok(technique.sequence.every((seal) => NINJA_SEALS[seal]), technique.id);
  technique.sequence.forEach((seal, i) => {
    usedSeals.add(seal);
    if (i) assert.notEqual(seal, technique.sequence[i - 1], `${technique.id} repeats a sign`);
  });
  if (technique.tier === 0) assert.ok(technique.sequence.every((seal) => NINJA_SEALS[seal].level === 1));
  sequenceKeys.add(technique.sequence.join(" "));
}
assert.equal(sequenceKeys.size, Object.keys(NINJA_TECHNIQUES).length, "unique sequences");
assert.equal(usedSeals.size, Object.keys(NINJA_SEALS).length, "every sign appears in a weave");
assert.equal(ninjaTechnique("unknown").id, NINJA_DEFAULT_TECHNIQUE);
assert.equal(ninjaTechniqueList("water").length, NINJA_FORMS.length);
assert.ok(ninjaTechniqueList("water").every((t) => t.element === "water"));

// Every finisher has a spec and a finite particle plan that stays near the stage.
const pathSignatures = new Set();
for (const id of Object.keys(NINJA_EFFECTS)) {
  const spec = ninjaEffectSpec(id);
  assert.equal(spec.id, id);
  assert.equal(spec.colors.length, 3);
  assert.ok(spec.pitch > 0.5 && spec.pitch < 1.5);
  const particles = ninjaEffectParticles(id, 18);
  assert.equal(particles.length, 18);
  for (const particle of particles) {
    assert.ok(particle.points.length >= 2);
    assert.ok(particle.delay >= 0 && particle.delay <= 1000);
    for (const point of particle.points) {
      assert.ok(Number.isFinite(point.x) && point.x >= -0.2 && point.x <= 1.2, id);
      assert.ok(Number.isFinite(point.y) && point.y >= -0.2 && point.y <= 1.2, id);
    }
  }
  pathSignatures.add(JSON.stringify(particles.map((p) => p.points)));
}
assert.equal(pathSignatures.size, Object.keys(NINJA_EFFECTS).length, "every effect moves differently");
assert.deepEqual(ninjaEffectParticles("fire-comet", 12), ninjaEffectParticles("fire-comet", 12));

const firstSeal = NINJA_TECHNIQUES[NINJA_DEFAULT_TECHNIQUE].sequence[0];
let forgiving = freshNinjaRun(NINJA_DEFAULT_TECHNIQUE, "family");
forgiving = advanceNinjaWeave(forgiving, {seal: firstSeal, now: 0});
assert.equal(forgiving.event, "hold");
forgiving = advanceNinjaWeave(forgiving, {seal: null, now: 80});
assert.equal(forgiving.event, "hold");
assert.ok(80 <= NINJA_HOLD_GRACE_MS);
forgiving = advanceNinjaWeave(forgiving, {seal: firstSeal, now: NINJA_HOLD_MS});
assert.equal(forgiving.event, "step");

const longest = Object.values(NINJA_TECHNIQUES).find((t) => t.sequence.length === 6);
let weave = freshNinjaRun(longest.id, "family");
let weaveNow = 0;
for (const expected of longest.sequence) {
  let step = advanceNinjaWeave(weave, {seal: expected, now: weaveNow});
  assert.equal(step.event, "hold");
  weaveNow += NINJA_HOLD_MS;
  step = advanceNinjaWeave(step, {seal: expected, now: weaveNow});
  weave = step;
  if (!weave.finished) {
    assert.equal(weave.event, "step");
    weaveNow += 1;
    weave = advanceNinjaWeave(weave, {seal: null, now: weaveNow});
    assert.equal(weave.event, "release");
    weaveNow += NINJA_RELEASE_MS;
    weave = advanceNinjaWeave(weave, {seal: null, now: weaveNow});
  }
  weaveNow += 1;
}
assert.equal(weave.finished, true);
assert.equal(weave.index, 6);
assert.equal(weave.bestCombo, 6);
assert.equal(weave.event, "done");

let wrongWeave = freshNinjaRun("water-wave", "sharp");
const notWanted = Object.keys(NINJA_SEALS).find((id) => id !== NINJA_TECHNIQUES["water-wave"].sequence[0]);
wrongWeave = advanceNinjaWeave(wrongWeave, {seal: notWanted, now: 10});
assert.equal(wrongWeave.event, "wrong");
wrongWeave = advanceNinjaWeave(wrongWeave, {seal: null, now: 60010});
assert.equal(wrongWeave.event, "waiting");
assert.equal(wrongWeave.combo, 0);
assert.equal(wrongWeave.index, 0);

// Fast movement can leave only a few tracker samples. Three brief samples are
// enough; they do not need to form one uninterrupted wall-clock hold.
let quickWeave = freshNinjaRun(NINJA_DEFAULT_TECHNIQUE, "family");
quickWeave = advanceNinjaWeave(quickWeave, {seal: firstSeal, now: 0});
quickWeave = advanceNinjaWeave(quickWeave, {seal: firstSeal, now: 35});
quickWeave = advanceNinjaWeave(quickWeave, {seal: firstSeal, now: 70});
assert.equal(quickWeave.event, "step");
assert.equal(quickWeave.index, 1);

// Dropouts and wrong intermediate poses preserve evidence for the requested
// sign. A player may also pause for any length of time between discrete signs.
let interrupted = freshNinjaRun(NINJA_DEFAULT_TECHNIQUE, "family");
interrupted = advanceNinjaWeave(interrupted, {seal: firstSeal, now: 0});
interrupted = advanceNinjaWeave(interrupted, {seal: notWanted, now: 70});
assert.equal(interrupted.event, "hold");
interrupted = advanceNinjaWeave(interrupted, {seal: null, now: 500});
assert.equal(interrupted.event, "hold");
interrupted = advanceNinjaWeave(interrupted, {seal: notWanted, now: 900});
assert.equal(interrupted.event, "hold");
interrupted = advanceNinjaWeave(interrupted, {seal: firstSeal, now: 1100});
assert.equal(interrupted.event, "step");

const secondSeal = NINJA_TECHNIQUES[NINJA_DEFAULT_TECHNIQUE].sequence[1];
const wrongForSecond = Object.keys(NINJA_SEALS).find((id) => id !== secondSeal && id !== firstSeal);
interrupted = advanceNinjaWeave(interrupted, {seal: wrongForSecond, now: 1200});
assert.equal(interrupted.event, "release");
interrupted = advanceNinjaWeave(interrupted, {seal: wrongForSecond, now: 1300});
assert.equal(interrupted.event, "wrong");
interrupted = advanceNinjaWeave(interrupted, {seal: null, now: 61300});
assert.equal(interrupted.event, "waiting");
assert.equal(interrupted.index, 1);
interrupted = advanceNinjaWeave(interrupted, {seal: secondSeal, now: 70000});
interrupted = advanceNinjaWeave(interrupted, {seal: secondSeal, now: 70120});
assert.equal(interrupted.event, "step");
assert.equal(interrupted.index, 2);

// --- 8. A Python-driven parity emitter --------------------------------------
// When invoked with --emit-math-rounds=<age>:<i0>,<i1>,..., print one JSON
// round per line so test_math_toss_fallback_matches_server() in Python can
// diff the Node output against math_toss_round() for byte-identical parity
// without re-implementing the round logic in Python.
const emitArg = process.argv.find((arg) => arg.startsWith("--emit-math-rounds="));
if (emitArg) {
  const spec = emitArg.slice("--emit-math-rounds=".length);
  for (const chunk of spec.split(";")) {
    const [age, indices] = chunk.split(":");
    if (!age || !indices) continue;
    for (const raw of indices.split(",")) {
      const i = Number(raw);
      if (!Number.isFinite(i)) continue;
      process.stdout.write(`${JSON.stringify(localMathRound(age, i))}\n`);
    }
  }
  process.exit(0);
}

console.log("vision geometry OK");

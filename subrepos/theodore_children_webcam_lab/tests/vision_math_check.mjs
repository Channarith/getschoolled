// Executed by test_gesture_geometry_is_distance_invariant.
//
// Builds synthetic MediaPipe-shaped hands, then places the SAME pose at
// different scales (child near / far from the camera) and rotations to prove
// classification does not change. The old fixed-distance thresholds failed
// exactly this: a distant child read as a permanent fist.
import assert from "node:assert/strict";
import {
  FIST_MAX_PALMS, FINGERTIP_LANDMARKS, HAND_BONES, SIGNAL_HOLD_MS, AWAY_HOLD_MS, RETURN_HOLD_MS,
  activeFingertips, advanceThrowGesture, catchRadiusPx, claimTouch, coverFrame, createPresenceWatch, fingersPointed,
  handShape, heartRatios, isHeartShape, mapMirroredLandmark, palmSpan, profileTouchAge,
  newThrowTracker, projectThrowTarget, syntheticHand, tipHitsTarget, traceProgress,
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

console.log("vision geometry OK");

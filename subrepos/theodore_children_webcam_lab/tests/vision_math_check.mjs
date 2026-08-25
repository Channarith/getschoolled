// Executed by test_gesture_geometry_is_distance_invariant.
//
// Builds synthetic MediaPipe-shaped hands, then places the SAME pose at
// different scales (child near / far from the camera) and rotations to prove
// classification does not change. The old fixed-distance thresholds failed
// exactly this: a distant child read as a permanent fist.
import assert from "node:assert/strict";
import {
  FIST_MAX_PALMS, handShape, heartRatios, isHeartShape, palmSpan, syntheticHand,
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

// --- 3. A heart needs tips together AND wrists apart, at any distance --------
function heartPose(scale) {
  // Two hands leaning in: index tips meet at the top, thumbs meet below, and
  // the wrists stay apart at the bottom.
  const left = place(canonicalHand({ curl: 0.35 }), {
    scale, angle: 0.5, at: { x: 0.42, y: 0.55 },
  });
  const right = place(canonicalHand({ curl: 0.35 }), {
    scale, angle: -0.5, at: { x: 0.58, y: 0.55 },
  });
  // Mirror the right hand so the two point at each other.
  const mirroredRight = right.map((p) => ({ x: 1.0 - p.x, y: p.y }));
  return [left, mirroredRight];
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
  for (const key of ["tips", "thumbs", "wrists"]) {
    assert.ok(
      Math.abs(ratios[key] - reference[key]) < 1e-6,
      `heart ${key} changed with camera distance: ${ratios[key]} vs ${reference[key]}`,
    );
  }
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

console.log("vision geometry OK");

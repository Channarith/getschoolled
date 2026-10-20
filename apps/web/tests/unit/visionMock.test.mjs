import test from "node:test";
import assert from "node:assert/strict";
import { cosineSimilarity, faceGeometry, poseFromBaseline } from "../../app/lib/learnerCheck.ts";
import { createMockVisionEngine } from "../../app/lib/visionMock.ts";

const POSE_MATCH_MIN = 0.24;
const SERVER_POSE_THRESHOLD = 0.22;

test("mock face walks through every look and each look matches the portrait", () => {
  let clock = 0;
  const engine = createMockVisionEngine(() => clock);
  const first = engine.detect()[0];
  const base = faceGeometry(first.landmarks, first.bbox, first.frame_size);
  assert.ok(base?.centered, "neutral face is centered");
  const neutral = engine.embedAt(null, first.landmarks);

  const seen = new Map();
  for (clock = 0; clock < 10_000; clock += 40) {
    const face = engine.detect()[0];
    const geometry = faceGeometry(face.landmarks, face.bbox, face.frame_size);
    const pose = poseFromBaseline(base, geometry);
    if (pose && !seen.has(pose)) seen.set(pose, engine.embedAt(null, face.landmarks));
  }
  assert.deepEqual([...seen.keys()].sort(), ["down", "left", "right", "up"]);
  for (const [pose, vector] of seen) {
    const score = cosineSimilarity(neutral, vector);
    assert.ok(score >= POSE_MATCH_MIN && score >= SERVER_POSE_THRESHOLD, `${pose} cosine ${score}`);
    const moved = vector.reduce((sum, value, i) => sum + (value - neutral[i]) ** 2, 0);
    assert.ok(moved > 1e-6, `${pose} is not a static frame`);
  }
});

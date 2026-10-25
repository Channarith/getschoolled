// Executed by tests/test_detect_health.py. Proves the failure handling that keeps a phone game playable
// when the face/hand models fail, load slowly, or return nothing, and that a "you left the camera" pause needs a healthy detector.
import assert from "node:assert/strict";
import {
  BLIND_MS_BEFORE_TOUCH, ERRORS_BEFORE_NEXT, FACE_BLIND_MS, HANDS_AFTER_FACE_MS, HANDS_BLIND_MS, HEALTHY_WINDOW_MS, createDetectHealth,
} from "../src/theodore_children_webcam_lab/static/detect_health.js";
import {
  FACE_VARIANTS, HAND_VARIANTS, createFirstWorking, faceOptions, handOptions, runHandTest, variantOf,
} from "../src/theodore_children_webcam_lab/static/vision_detectors.js";

let t = 0;
const clock = () => t;
const fresh = () => { t = 0; return createDetectHealth({now: clock, variants: {face: FACE_VARIANTS.length, hands: HAND_VARIANTS.length}}); };

// 1. Still loading: no model yet, nothing is "away", no fallback.
{
  const h = fresh();
  assert.equal(h.presenceAllowed(), false);
  assert.equal(h.touchFallback(), "");
  assert.equal(h.loading(), true);
}

// 2. Both models failed to load: play by touch, silently, and never claim the player left.
{
  const h = fresh();
  h.fail("face", "wasm 404"); h.fail("hands", "gpu init");
  assert.equal(h.touchFallback(), "no-model");
  assert.equal(h.presenceAllowed(), false);
}

// 3. Presence needs a face seen once AND a detector that is running healthily right now.
{
  const h = fresh();
  h.register("face", "GPU", 0, "gpu-blend"); h.register("hands", "GPU", 0, "gpu");
  for (let i = 0; i < 100; i++) { t += 33; h.run("face", {ok: true, found: false}); }
  assert.equal(h.presenceAllowed(), false, "a detector that never saw a face must not pause the lesson");
  t += 33; h.run("face", {ok: true, found: true});
  assert.equal(h.presenceAllowed(), true);
  // the detector stops producing frames (not running): absence means nothing
  t += HEALTHY_WINDOW_MS + 50;
  assert.equal(h.presenceAllowed(), false, "no frames lately: not healthy, so no 'left the camera'");
  h.run("face", {ok: true, found: false});
  assert.equal(h.presenceAllowed(), true, "healthy again, face absent: the pause logic may now apply");
  // errors make it unhealthy
  h.run("face", {ok: false, error: "x"});
  assert.equal(h.presenceAllowed(), false);
}

// 4. Face ladder: GPU+blendshapes throws -> next variant (GPU, no blendshapes, what /diag used), then CPU. Never past the end.
{
  const h = fresh();
  h.register("face", "GPU", 0, "gpu-blend");
  for (let i = 0; i < ERRORS_BEFORE_NEXT - 1; i++) h.run("face", {ok: false, error: "gl lost"});
  assert.equal(h.fallbackWanted("face"), -1);
  h.run("face", {ok: false, error: "gl lost"});
  assert.equal(h.fallbackWanted("face"), 1);
  h.markVariant("face", 1, "gpu", "GPU");
  for (let i = 0; i < ERRORS_BEFORE_NEXT; i++) h.run("face", {ok: false, error: "gl lost"});
  assert.equal(h.fallbackWanted("face"), 2);
  h.markVariant("face", 2, "cpu", "CPU");
  for (let i = 0; i < ERRORS_BEFORE_NEXT; i++) h.run("face", {ok: false, error: "still"});
  assert.equal(h.fallbackWanted("face"), -1, "the ladder ends at the last variant");
  assert.equal(h.touchFallback(), "detector-errors");
}

// 5. A face model that runs but never finds a face moves down the ladder after FACE_BLIND_MS.
{
  const h = fresh();
  h.register("face", "GPU", 0, "gpu-blend");
  h.run("face", {ok: true, found: false});
  t += FACE_BLIND_MS - 1; h.run("face", {ok: true, found: false});
  assert.equal(h.fallbackWanted("face"), -1);
  t += 2; h.run("face", {ok: true, found: false});
  assert.equal(h.fallbackWanted("face"), 1);
}

// 6. Hands are judged blind only once a face has been working (a person is plainly there). Then the ladder walks.
{
  const h = fresh();
  h.register("face", "GPU", 0, "gpu-blend"); h.register("hands", "GPU", 0, "gpu");
  h.run("hands", {ok: true, found: false});
  t += HANDS_BLIND_MS + 1000; h.run("hands", {ok: true, found: false});
  assert.equal(h.fallbackWanted("hands"), -1, "no face yet: the player may simply not be there");
  h.run("face", {ok: true, found: true});
  t += HANDS_AFTER_FACE_MS - 10; h.run("hands", {ok: true, found: false});
  assert.equal(h.fallbackWanted("hands"), -1, "face has not been working long enough");
  t += 20; h.run("hands", {ok: true, found: false});
  assert.equal(h.fallbackWanted("hands"), 1, "gpu -> cpu");
  h.markVariant("hands", 1, "cpu", "CPU");
  h.run("hands", {ok: true, found: false});   // the new variant starts its own blind clock on its first frame
  t += HANDS_BLIND_MS + 1; h.run("face", {ok: true, found: true}); h.run("hands", {ok: true, found: false});
  assert.equal(h.fallbackWanted("hands"), 2, "cpu -> cpu-low (lower thresholds)");
  h.markVariant("hands", 2, "cpu-low", "CPU");
  h.run("hands", {ok: true, found: true});
  assert.equal(h.sawHand(), true);
  assert.equal(h.summary().hands.foundByVariant["cpu-low"], 1, "the variant that finally saw a hand is recorded");
  t += HANDS_BLIND_MS * 3; h.run("hands", {ok: true, found: false});
  assert.equal(h.fallbackWanted("hands"), -1, "once a hand was seen the ladder stops");
}

// 7. Everything blind on the last variants: play by touch quietly; a later detection ends the fallback.
{
  const h = fresh();
  h.register("face", "CPU", FACE_VARIANTS.length - 1, "cpu"); h.register("hands", "CPU", HAND_VARIANTS.length - 1, "cpu-canvas");
  h.run("face", {ok: true}); h.run("hands", {ok: true});
  t += BLIND_MS_BEFORE_TOUCH - 10; h.run("face", {ok: true}); h.run("hands", {ok: true});
  assert.equal(h.touchFallback(), "");
  t += 20; h.run("face", {ok: true}); h.run("hands", {ok: true});
  assert.equal(h.touchFallback(), "no-detections");
  h.run("hands", {ok: true, found: true});
  assert.equal(h.touchFallback(), "");
}

// 8. The variant tables: same shape for the game and /diag/vision; diag's old face recipe is variant 1; hand ladder has lower thresholds and a canvas feed.
{
  assert.equal(FACE_VARIANTS[0].blendshapes, true);
  assert.equal(FACE_VARIANTS[1].blendshapes, false);
  assert.ok(HAND_VARIANTS.some((v) => v.conf < 0.5), "a low-threshold hand variant exists");
  assert.ok(HAND_VARIANTS.some((v) => v.feed === "canvas"), "a canvas-fed hand variant exists");
  const ctx = {modelBase: (key, path, delegate) => ({key, path, delegate}), source: {face: "f.task", hand: "h.task"}};
  const fo = faceOptions(ctx, FACE_VARIANTS[1]);
  assert.equal(fo.outputFaceBlendshapes, false);
  assert.equal(fo.baseOptions.delegate, "GPU");
  const ho = handOptions(ctx, HAND_VARIANTS[2]);
  assert.equal(ho.numHands, 2);
  assert.equal(ho.minHandDetectionConfidence, 0.3);
  assert.equal(ho.baseOptions.delegate, "CPU");
  assert.equal(variantOf(HAND_VARIANTS, 99), HAND_VARIANTS.at(-1));
}

// 9. createFirstWorking skips the other GPU variants once a GPU create fails, and reports every error.
{
  const tried = [];
  const list = [{id: "a", delegate: "GPU"}, {id: "b", delegate: "GPU"}, {id: "c", delegate: "CPU"}];
  const result = await createFirstWorking(list, async (v) => { tried.push(v.id); if (v.delegate === "GPU") throw new Error("no gpu"); return {id: v.id}; });
  assert.deepEqual(tried, ["a", "c"]);
  assert.equal(result.index, 2);
  assert.equal(result.errors.length, 1);
  const none = await createFirstWorking(list, async () => { throw new Error("nope"); });
  assert.equal(none.model, null);
}

// 10. The /diag/vision hand test reports which variant sees a hand, with fake models: only the CPU low-threshold one does.
{
  let created = [];
  const ctx = {
    files: {}, source: {}, modelBase: (key, path, delegate) => ({delegate}),
    vision: {HandLandmarker: {createFromOptions: async (files, opts) => {
      const low = opts.minHandDetectionConfidence < 0.4 && opts.baseOptions.delegate === "CPU";
      created.push(`${opts.baseOptions.delegate}${opts.minHandDetectionConfidence}`);
      return {detectForVideo: () => ({landmarks: low ? [[{x: 0, y: 0}]] : []}), close() {}};
    }}},
  };
  let clock2 = 0;
  const report = await runHandTest({
    ctx, video: {readyState: 4, videoWidth: 640, videoHeight: 480}, seconds: 1, now: () => clock2,
    nextFrame: async () => { clock2 += 100; },
  });
  assert.equal(report.rows.length, HAND_VARIANTS.length);
  assert.equal(report.saw, true);
  assert.equal(report.winner, "cpu-low");
  assert.ok(report.rows.every((r) => r.frames > 0));
  assert.equal(report.rows.find((r) => r.id === "cpu-low").withHit > 0, true);
}
console.log("detect health ok");

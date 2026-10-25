// Executed by tests/test_detect_health.py. Proves the failure handling that keeps a phone game playable
// when the face/hand models fail, load slowly, or return nothing.
import assert from "node:assert/strict";
import {
  BLIND_MS_BEFORE_CPU, BLIND_MS_BEFORE_TOUCH, ERRORS_BEFORE_CPU, createDetectHealth,
} from "../src/theodore_children_webcam_lab/static/detect_health.js";

let t = 0;
const clock = () => t;
const fresh = () => { t = 0; return createDetectHealth({now: clock}); };

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
  assert.equal(h.loading(), false);
}

// 3. Presence is only judged after the detector has seen this person at least once.
{
  const h = fresh();
  h.register("face", "GPU"); h.register("hands", "GPU");
  for (let i = 0; i < 100; i++) { t += 33; h.run("face", {ok: true, found: false}); }
  assert.equal(h.presenceAllowed(), false, "a detector that never saw a face must not pause the lesson");
  t += 33; h.run("face", {ok: true, found: true});
  assert.equal(h.presenceAllowed(), true);
  assert.equal(h.touchFallback(), "");
}

// 4. GPU delegate throws every frame: rebuild on CPU after ERRORS_BEFORE_CPU, and only once.
{
  const h = fresh();
  h.register("face", "GPU");
  for (let i = 0; i < ERRORS_BEFORE_CPU - 1; i++) h.run("face", {ok: false, error: "gl lost"});
  assert.equal(h.fallbackWanted("face"), "");
  h.run("face", {ok: false, error: "gl lost"});
  assert.equal(h.fallbackWanted("face"), "cpu");
  h.markFallback("face");
  assert.equal(h.fallbackWanted("face"), "", "no second rebuild");
  assert.equal(h.summary().face.delegate, "CPU");
}

// 5. GPU model runs fine but returns nothing for BLIND_MS_BEFORE_CPU: try the CPU once.
{
  const h = fresh();
  h.register("hands", "GPU");
  h.run("hands", {ok: true, found: false});
  t += BLIND_MS_BEFORE_CPU - 1; h.run("hands", {ok: true, found: false});
  assert.equal(h.fallbackWanted("hands"), "");
  t += 2; h.run("hands", {ok: true, found: false});
  assert.equal(h.fallbackWanted("hands"), "cpu");
}

// 6. CPU is blind too for BLIND_MS_BEFORE_TOUCH: switch to screen touch quietly; seeing a person later restores tracking.
{
  const h = fresh();
  h.register("face", "CPU"); h.register("hands", "CPU");
  h.run("face", {ok: true}); h.run("hands", {ok: true});
  t += BLIND_MS_BEFORE_TOUCH - 10; h.run("face", {ok: true}); h.run("hands", {ok: true});
  assert.equal(h.touchFallback(), "");
  t += 20; h.run("face", {ok: true}); h.run("hands", {ok: true});
  assert.equal(h.touchFallback(), "no-detections");
  h.run("hands", {ok: true, found: true});
  assert.equal(h.touchFallback(), "", "a detected hand ends the touch fallback");
  assert.equal(h.sawPerson(), true);
}

// 7. CPU errors (not GPU) report detector-errors immediately; summary is loggable and holds no frames.
{
  const h = fresh();
  h.register("face", "CPU");
  for (let i = 0; i < ERRORS_BEFORE_CPU; i++) h.run("face", {ok: false, error: "x".repeat(400)});
  assert.equal(h.touchFallback(), "detector-errors");
  const s = JSON.stringify(h.summary());
  assert.ok(s.length < 700 && !/ImageData|Uint8/.test(s));
}
console.log("detect health ok");

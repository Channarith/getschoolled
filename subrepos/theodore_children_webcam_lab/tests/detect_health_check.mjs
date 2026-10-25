// Executed by tests/test_detect_health.py. Proves the failure handling that keeps a phone game playable when the face/hand models fail,
// load slowly, or return nothing; that a "you left the camera" pause needs a healthy detector; and the per-device rules, recipe cache and
// self-healing controller, using what the two real phones measured:
//   Android, Chrome 156, Adreno 830:  face gpu 53/54, gpu+blendshapes 52/57, CPU 0/59; hands GPU 0/82 (also at 0.3 and with a canvas feed), hands CPU 71/71.
//   iPhone, Safari, iOS 18.7, Apple GPU: face gpu+blendshapes STALLS (1 frame in ~9 s), gpu 44/44, cpu 58/58; hands GPU 0.5 1/1 (slow warm-up), gpu 0.3 46/46, cpu 40/40.
import assert from "node:assert/strict";
import {
  BLIND_MS_BEFORE_TOUCH, CACHE_BLIND_FRAMES, ERRORS_BEFORE_NEXT, FACE_BLIND_MS, FACE_MIN_BLIND_FRAMES, HANDS_AFTER_FACE_MS, HANDS_BLIND_MS,
  HANDS_MIN_BLIND_FRAMES, HEALTHY_WINDOW_MS, createDetectHealth,
} from "../src/theodore_children_webcam_lab/static/detect_health.js";
import {
  BLEND_WATCHDOG_MS, EXPRESSION_GAMES, FACE_BLEND_VARIANT, FACE_VARIANTS, FOUND_FRAMES_TO_REMEMBER, HAND_VARIANTS, KNOWN_BAD_RULES, MIN_WINNER_FRAMES,
  buildLadders, createDetectorController, createFirstWorking, createRecipeCache, detectEnv, faceOptions, handOptions, hashText, memoryStorage,
  pickWinner, runHandTest, variantOf,
} from "../src/theodore_children_webcam_lab/static/vision_detectors.js";

let t = 0;
const clock = () => t;
const fresh = (warmupMs = 0) => { t = 0; return createDetectHealth({now: clock, variants: {face: FACE_VARIANTS.length, hands: HAND_VARIANTS.length}, warmupMs}); };
// `n` processed frames, 33 ms apart.
const frames = (h, name, n, found = false) => { for (let i = 0; i < n; i++) { t += 33; h.run(name, {ok: true, found}); } };

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
  h.register("face", "GPU", 0, "gpu"); h.register("hands", "GPU", 0, "gpu");
  frames(h, "face", 100);
  assert.equal(h.presenceAllowed(), false, "a detector that never saw a face must not pause the lesson");
  frames(h, "face", 1, true);
  assert.equal(h.presenceAllowed(), true);
  t += HEALTHY_WINDOW_MS + 50;
  assert.equal(h.presenceAllowed(), false, "no frames lately: not healthy, so no 'left the camera'");
  frames(h, "face", 1);
  assert.equal(h.presenceAllowed(), true, "healthy again, face absent: the pause logic may now apply");
  h.run("face", {ok: false, error: "x"});
  assert.equal(h.presenceAllowed(), false);
}

// 4. Face ladder (gpu -> gpu-low -> cpu): errors move one rung at a time and never past the end.
{
  const h = fresh();
  h.register("face", "GPU", 0, "gpu");
  for (let i = 0; i < ERRORS_BEFORE_NEXT - 1; i++) h.run("face", {ok: false, error: "gl lost"});
  assert.equal(h.fallbackWanted("face"), -1);
  h.run("face", {ok: false, error: "gl lost"});
  assert.equal(h.fallbackWanted("face"), 1);
  h.markVariant("face", 1, "gpu-low", "GPU");
  for (let i = 0; i < ERRORS_BEFORE_NEXT; i++) h.run("face", {ok: false, error: "gl lost"});
  assert.equal(h.fallbackWanted("face"), 2);
  h.markVariant("face", 2, "cpu", "CPU");
  for (let i = 0; i < ERRORS_BEFORE_NEXT; i++) h.run("face", {ok: false, error: "still"});
  assert.equal(h.fallbackWanted("face"), -1, "the ladder ends at the last variant");
  assert.equal(h.touchFallback(), "detector-errors");
}

// 5. A face model that runs but never finds a face steps down only after enough FRAMES and time (warm-up tolerant).
{
  const h = fresh();
  h.register("face", "GPU", 0, "gpu");
  frames(h, "face", 1);
  t += FACE_BLIND_MS + 100; frames(h, "face", FACE_MIN_BLIND_FRAMES - 5);
  assert.equal(h.fallbackWanted("face"), -1, "too few frames processed: slow to start, not blind");
  frames(h, "face", 10);
  assert.equal(h.fallbackWanted("face"), 1);
  // iOS: the same model gets 10 more seconds of warm-up before anyone may call it blind
  const ios = fresh(10000);
  ios.register("face", "GPU", 0, "gpu");
  frames(ios, "face", 1);
  t += FACE_BLIND_MS + 100; frames(ios, "face", FACE_MIN_BLIND_FRAMES + 10);
  assert.equal(ios.fallbackWanted("face"), -1, "still inside the iOS warm-up window");
  t += 10000; frames(ios, "face", 1);
  assert.equal(ios.fallbackWanted("face"), 1);
}

// 6. Hands are judged blind only once a face has been working (a person is plainly there), after enough frames. Then the ladder walks.
{
  const h = fresh();
  h.register("face", "GPU", 0, "gpu"); h.register("hands", "GPU", 0, "gpu");
  frames(h, "hands", HANDS_MIN_BLIND_FRAMES + 5);
  t += HANDS_BLIND_MS + 1000; frames(h, "hands", 1);
  assert.equal(h.fallbackWanted("hands"), -1, "no face yet: the player may simply not be there");
  frames(h, "face", 1, true);
  t += HANDS_AFTER_FACE_MS - 200; frames(h, "hands", 1);
  assert.equal(h.fallbackWanted("hands"), -1, "face has not been working long enough");
  t += 200; frames(h, "hands", 1);
  assert.equal(h.fallbackWanted("hands"), 1, "gpu -> next rung");
  h.markVariant("hands", 1, "gpu-low", "GPU");
  frames(h, "hands", HANDS_MIN_BLIND_FRAMES + 1);
  t += HANDS_BLIND_MS + 1; frames(h, "face", 1, true); frames(h, "hands", 1);
  assert.equal(h.fallbackWanted("hands"), 2);
  h.markVariant("hands", 2, "cpu", "CPU");
  frames(h, "hands", 1, true);
  assert.equal(h.sawHand(), true);
  assert.equal(h.summary().hands.foundByVariant.cpu, 1, "the variant that finally saw a hand is recorded");
  t += HANDS_BLIND_MS * 3; frames(h, "hands", HANDS_MIN_BLIND_FRAMES + 1);
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

// 8. Variant tables: plain face first (blendshapes are opt-in), hands at confidence 0.4 with lower and canvas variants available.
{
  assert.ok(FACE_VARIANTS.every((v) => v.blendshapes === false), "no default face recipe uses blendshapes");
  assert.equal(FACE_VARIANTS[0].id, "gpu");
  assert.equal(FACE_VARIANTS.at(-1).delegate, "CPU", "CPU face is the last rung");
  assert.equal(FACE_BLEND_VARIANT.blendshapes, true);
  assert.equal(FACE_BLEND_VARIANT.optIn, true);
  assert.equal(HAND_VARIANTS[0].conf, 0.4, "hands start at 0.4 everywhere");
  assert.ok(HAND_VARIANTS.some((v) => v.conf === 0.3), "a low-threshold hand variant exists");
  assert.ok(HAND_VARIANTS.some((v) => v.feed === "canvas"), "a canvas-fed hand variant exists");
  for (const game of ["popcorn", "wow", "wink", "blow-kiss", "oh-behave"]) assert.ok(EXPRESSION_GAMES.has(game));
  assert.equal(EXPRESSION_GAMES.has("pop-quiz-toss"), false, "the quiz needs no expressions");
  const ctx = {modelBase: (key, path, delegate) => ({key, path, delegate}), source: {face: "f.task", hand: "h.task"}};
  const fo = faceOptions(ctx, FACE_VARIANTS[0]);
  assert.equal(fo.outputFaceBlendshapes, false);
  assert.equal(faceOptions(ctx, FACE_BLEND_VARIANT).outputFaceBlendshapes, true);
  const ho = handOptions(ctx, HAND_VARIANTS[3]);
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
  assert.equal((await createFirstWorking(list, async () => { throw new Error("nope"); })).model, null);
}

// 10. The /diag/vision hand test reports which variant sees a hand, with fake models: only the CPU low-threshold one does.
{
  const ctx = {
    files: {}, source: {}, modelBase: (key, path, delegate) => ({delegate}),
    vision: {HandLandmarker: {createFromOptions: async (files, opts) => {
      const low = opts.minHandDetectionConfidence < 0.4 && opts.baseOptions.delegate === "CPU";
      return {detectForVideo: () => ({landmarks: low ? [[{x: 0, y: 0}]] : []}), close() {}};
    }}},
  };
  let clock2 = 0;
  const report = await runHandTest({ctx, video: {readyState: 4, videoWidth: 640, videoHeight: 480}, seconds: 2, now: () => clock2, nextFrame: async () => { clock2 += 100; }});
  assert.equal(report.rows.length, HAND_VARIANTS.length);
  assert.equal(report.saw, true);
  assert.equal(report.winner, "cpu-low");
  assert.ok(report.rows.filter((r) => r.feed !== "canvas").every((r) => r.frames >= MIN_WINNER_FRAMES), JSON.stringify(report.rows));   // canvas rows need a real <canvas>
}

// ---- Device rules, ladders, recipe cache and the self-healing controller ----
const ANDROID_ADRENO = {
  ua: "Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.7600.0 Mobile Safari/537.36",
  renderer: "ANGLE (Qualcomm, Adreno (TM) 830, OpenGL ES 3.2)",
};
const IPHONE_SAFARI = {
  ua: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.7 Mobile/15E148 Safari/604.1",
  renderer: "Apple GPU",
};
const IPHONE_CHROME = {ua: IPHONE_SAFARI.ua.replace("Version/18.7", "CriOS/156.0.0.0 Version/18.7"), renderer: "Apple GPU"};
const DESKTOP_NVIDIA = {
  ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.7600.0 Safari/537.36",
  renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090, OpenGL 4.1)",
};
const firstId = (list) => list[0].id;
const newHealth = (env) => { t = 0; return createDetectHealth({now: clock, variants: {face: FACE_VARIANTS.length, hands: HAND_VARIANTS.length}, warmupMs: env.warmupMs}); };

// 11. Device rules. The known-bad rule is Qualcomm Adreno only; Android Chromium starts hands on the CPU by default; iOS and desktop are never forced.
{
  const phone = detectEnv(ANDROID_ADRENO);
  assert.equal(phone.androidChromium, true);
  assert.equal(phone.browser, "Chrome/156");
  assert.ok(phone.rules.includes("gpu-hand-adreno"), "the known-bad rule that matched is named");
  assert.ok(phone.rules.some((r) => r.startsWith("android-chromium")));
  const l = buildLadders(phone, {});
  assert.equal(l.face[0].id, "gpu", "face stays GPU first, without blendshapes");
  assert.equal(l.face[0].blendshapes, false);
  assert.deepEqual(l.hands.map((v) => v.delegate), ["CPU", "CPU", "CPU", "GPU", "GPU", "GPU"], "hands start on the CPU; GPU hand variants are a last resort");
  assert.equal(l.face.at(-1).delegate, "CPU");

  const desktop = detectEnv(DESKTOP_NVIDIA);
  assert.deepEqual(desktop.rules, []);
  assert.equal(firstId(buildLadders(desktop, {}).hands), "gpu", "desktop keeps the GPU hand default");

  // an Adreno GPU in a desktop browser (Windows on ARM) matches the known-bad rule; nothing else does
  const arm = detectEnv({ua: DESKTOP_NVIDIA.ua, renderer: "ANGLE (Qualcomm, Adreno (TM) X1-85, D3D11)"});
  assert.deepEqual(arm.rules, ["gpu-hand-adreno"]);
  assert.equal(firstId(buildLadders(arm, {}).hands), "cpu");
  for (const renderer of ["Apple GPU", "ANGLE (NVIDIA, GeForce RTX 4090)", "ANGLE (ARM, Mali-G720)", "ANGLE (Intel, Intel(R) UHD Graphics)", ""]) {
    assert.deepEqual(detectEnv({ua: DESKTOP_NVIDIA.ua, renderer}).knownBad.hands, {}, `no known-bad rule for "${renderer}"`);
  }
  // Android on another GPU: CPU-first default, but no known-bad rule is claimed
  const mali = detectEnv({ua: ANDROID_ADRENO.ua, renderer: "ANGLE (ARM, Mali-G720, OpenGL ES 3.2)"});
  assert.equal(mali.rules.length, 1);
  assert.equal(firstId(buildLadders(mali, {}).hands), "cpu");
  assert.equal(KNOWN_BAD_RULES.length, 1);
  assert.equal(KNOWN_BAD_RULES[0].id, "gpu-hand-adreno");

  // iPhone (Safari AND Chrome-on-iOS, which is WebKit): never forced; hands GPU first; a 10 s warm-up window
  for (const iphone of [IPHONE_SAFARI, IPHONE_CHROME]) {
    const ios = detectEnv(iphone);
    assert.equal(ios.ios, true);
    assert.equal(ios.androidChromium, false);
    assert.deepEqual(ios.rules, [], "no rule is forced on iOS");
    assert.equal(ios.handsCpuFirst, false);
    assert.equal(ios.warmupMs, 12000, "generous first-result allowance on iOS");
    const il = buildLadders(ios, {});
    assert.equal(il.hands[0].id, "gpu");
    assert.equal(il.hands[0].conf, 0.4);
    assert.equal(il.face[0].id, "gpu");
  }
}

// 12. Recipe cache: keyed by GPU renderer + browser major version; a browser update or another phone is a miss; entries prune.
{
  let clock3 = 1000;
  const store = memoryStorage();
  const cache = createRecipeCache(store, () => clock3);
  const env = detectEnv(ANDROID_ADRENO);
  const none = {face: "", hands: "", blend: ""};
  assert.deepEqual(cache.load(env), none);
  cache.save(env, "face", "gpu"); cache.save(env, "hands", "cpu");
  assert.deepEqual(cache.load(env), {face: "gpu", hands: "cpu", blend: ""});
  assert.equal(env.key, hashText(`${ANDROID_ADRENO.renderer}|Chrome/156`));
  const updated = detectEnv({...ANDROID_ADRENO, ua: ANDROID_ADRENO.ua.replace("Chrome/156", "Chrome/157")});
  assert.deepEqual(cache.load(updated), none, "a browser update re-learns");
  cache.save(updated, "hands", "cpu-low");
  assert.deepEqual(cache.load(env), none, "the old version's entry is gone");
  assert.deepEqual(cache.load(detectEnv({ua: ANDROID_ADRENO.ua, renderer: "ANGLE (ARM, Mali-G720)"})), none, "another phone is another key");
  assert.equal(cache.drop(updated, "hands"), true);
  assert.deepEqual(cache.load(updated), none);
  createRecipeCache({getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); }, removeItem: () => {}}).save(env, "hands", "cpu");   // never throws
  const l = buildLadders(env, {face: "gpu-low", hands: "cpu-low"});
  assert.equal(l.face[0].id, "gpu-low"); assert.equal(l.hands[0].id, "cpu-low"); assert.deepEqual(l.fromCache, {face: true, hands: true});
  const bad = buildLadders(env, {hands: "gpu-low"});
  assert.equal(bad.fromCache.hands, false);
  assert.match(bad.ignored[0].why, /gpu-hand-adreno/);
  assert.equal(bad.hands[0].delegate, "CPU");
  // an iPhone is allowed to remember a GPU hand recipe
  assert.equal(buildLadders(detectEnv(IPHONE_SAFARI), {hands: "gpu-low"}).hands[0].id, "gpu-low");
}

// ---- stub landmarkers ----
// opts: gpuHandsBlind (Adreno), gpuFaceBlindAtDefault (face only sees at confidence < 0.5), blend: "ok" | "stall" | "throw",
// firstCallMs (iOS: the first inference of a new model takes seconds), cpuFaceWorks.
function makeCtx({gpuHandsBlind = true, gpuFaceBlindAtDefault = false, blend = "ok", firstCallMs = 0, cpuFaceWorks = false, handsBlindFrames = 0} = {}) {
  const created = [];
  const person = (kind) => (kind === "face" ? {faceLandmarks: [[{x: 0.5, y: 0.5}]]} : {landmarks: [[{x: 0.5, y: 0.5}], [{x: 0.6, y: 0.5}]]});
  const empty = (kind) => (kind === "face" ? {faceLandmarks: []} : {landmarks: []});
  const stub = (kind, opts) => {
    let calls = 0;
    return {
      close() {},
      detectForVideo: () => {
        calls++;
        if (calls === 1 && firstCallMs) t += firstCallMs;
        const gpu = opts.baseOptions.delegate === "GPU";
        if (kind === "hands") return (gpu && gpuHandsBlind) || calls <= handsBlindFrames ? empty(kind) : person(kind);
        if (opts.outputFaceBlendshapes) {
          if (blend === "throw") throw new Error("blendshapes failed");
          if (blend === "stall") { t += 5000; return empty(kind); }
        }
        if (gpu) return gpuFaceBlindAtDefault && opts.minFaceDetectionConfidence >= 0.5 ? empty(kind) : person(kind);
        return cpuFaceWorks ? person(kind) : empty(kind);
      },
    };
  };
  return {
    created, files: {}, source: {}, modelBase: (key, path, delegate) => ({delegate}),
    vision: {
      FaceLandmarker: {createFromOptions: async (files, opts) => { created.push(`face:${opts.baseOptions.delegate}${opts.outputFaceBlendshapes ? "+blend" : ""}@${opts.minFaceDetectionConfidence}`); return stub("face", opts); }},
      HandLandmarker: {createFromOptions: async (files, opts) => { created.push(`hands:${opts.baseOptions.delegate}@${opts.minHandDetectionConfidence}`); return stub("hands", opts); }},
    },
  };
}
const VIDEO = {readyState: 4, videoWidth: 640, videoHeight: 480};
const pass = (video) => video;
const build = (env, ctx, store, extra = {}) => {
  const health = newHealth(env);
  const events = [];
  const controller = createDetectorController({
    ctx, env, ladders: buildLadders(env, createRecipeCache(store).load(env)), health, cache: createRecipeCache(store, () => t), frameFor: pass, now: clock,
    onEvent: (type, d) => events.push([type, d]), ...extra,
  });
  return {health, events, controller};
};
// Run `seconds` of 30 fps frames, ticking like the game does (every 400 ms).
async function play(controller, seconds, {faceToo = true} = {}) {
  const n = Math.round(seconds * 30);
  let lastTick = t;
  for (let i = 0; i < n; i++) {
    t += 33;
    if (faceToo) controller.detect("face", VIDEO, t);
    controller.detect("hands", VIDEO, t);
    if (t - lastTick >= 400) { lastTick = t; await controller.tick(); }
  }
}
const ids = (events, type) => events.filter(([e]) => e === type).map(([, d]) => d);

// 13. THE ANDROID CASE: Adreno -> hands start on the CPU at once: no waiting, no user action, and no GPU hand model is ever built.
{
  const env = detectEnv(ANDROID_ADRENO);
  const ctx = makeCtx();
  const store = memoryStorage();
  const {health, events, controller: c} = build(env, ctx, store);
  await c.init();
  assert.equal(c.variantId("face"), "gpu");
  assert.equal(c.variantId("hands"), "cpu");
  assert.ok(!ctx.created.some((x) => x.startsWith("hands:GPU")), "no GPU hand model was built");
  assert.ok(!ctx.created.some((x) => x.includes("+blend")), "no blendshape model either");
  assert.ok(ids(events, "detector env")[0].rules.includes("gpu-hand-adreno"), "which rule matched is logged");
  await play(c, 2);
  assert.equal(health.sawHand(), true);
  assert.equal(health.sawFace(), true);
  assert.equal(health.touchFallback(), "");
  assert.deepEqual(createRecipeCache(store).load(env), {face: "gpu", hands: "cpu", blend: ""}, "what worked is remembered for this device");
}

// 14. THE IPHONE CASE: nothing is forced. GPU hands at 0.4, plain GPU face, a 9 s first inference is warm-up, and nothing is stepped down.
{
  const env = detectEnv(IPHONE_SAFARI);
  const ctx = makeCtx({gpuHandsBlind: false, firstCallMs: 9000, handsBlindFrames: 8});   // slow first call; the first few hand frames are empty
  const store = memoryStorage();
  const {health, events, controller: c} = build(env, ctx, store);
  await c.init();
  assert.equal(c.variantId("face"), "gpu");
  assert.equal(c.variantId("hands"), "gpu");
  assert.equal(ctx.created.filter((x) => x.startsWith("hands:")).length, 1);
  await play(c, 20);
  assert.equal(c.variantId("hands"), "gpu", "a working GPU hand model that was slow to start is NOT stepped down");
  assert.equal(c.variantId("face"), "gpu");
  assert.equal(ids(events, "detector variant").length, 0, "no rebuild happened");
  assert.equal(health.sawHand(), true);
  assert.equal(health.touchFallback(), "");
  assert.equal(ctx.created.filter((x) => x.startsWith("hands:")).length, 1, "the hand model was built exactly once");
}

// 15. SELF-HEALING with no rule: a device whose GPU hand model is blind. Hands start on GPU, the face works, and the game rebuilds hands
// by itself (gpu -> gpu-low -> cpu), remembers the winner, and the next launch skips the ladder.
{
  const env = detectEnv(DESKTOP_NVIDIA);
  const store = memoryStorage();
  const ctx = makeCtx();
  const {health, controller: c} = build(env, ctx, store);
  await c.init();
  assert.equal(c.variantId("hands"), "gpu");
  await play(c, 2);
  assert.equal(health.sawHand(), false, "the GPU hand model is blind");
  assert.equal(c.variantId("hands"), "gpu", "not switched yet: the face has not worked long enough");
  await play(c, 70);
  assert.equal(c.variantId("hands"), "cpu", "rebuilt on the CPU without any user action");
  assert.equal(health.sawHand(), true);
  assert.equal(createRecipeCache(store).load(env).hands, "cpu");
  assert.equal(c.variantId("face"), "gpu", "the working GPU face was never swapped for the CPU one");
  assert.ok(!ctx.created.includes("face:CPU@0.5"), "no CPU face model was built");

  const ctx2 = makeCtx();
  const second = build(env, ctx2, store);
  await second.controller.init();
  assert.equal(second.controller.variantId("hands"), "cpu");
  assert.equal(second.controller.isCached("hands"), true);
  assert.ok(!ctx2.created.some((x) => x.startsWith("hands:GPU")), "the blind GPU recipe was never tried again");
  await play(second.controller, 1);
  assert.equal(second.health.sawHand(), true);
}

// 16. A REMEMBERED recipe that goes blind (e.g. a driver update) is forgotten after CACHE_BLIND_FRAMES and the ladder resumes.
{
  const env = detectEnv(DESKTOP_NVIDIA);
  const store = memoryStorage();
  createRecipeCache(store).save(env, "hands", "gpu");        // remembered as working...
  const ctx = makeCtx({gpuHandsBlind: true});                 // ...but it is blind now
  const {health, events, controller: c} = build(env, ctx, store);
  await c.init();
  assert.equal(c.isCached("hands"), true);
  await play(c, (CACHE_BLIND_FRAMES / 30) + 3);
  assert.notEqual(c.variantId("hands"), "gpu", "moved off the stale remembered recipe");
  assert.ok(ids(events, "detector forgot remembered recipe").length >= 1);
  await play(c, 70);
  assert.equal(health.sawHand(), true);
  assert.equal(createRecipeCache(store).load(env).hands, c.variantId("hands"), "the recipe that works now replaced the stale one");
}

// 17. Face: when the default GPU recipe is blind (it only sees at confidence 0.3), gpu-low is tried BEFORE the CPU model; a working GPU face is never replaced.
{
  const env = detectEnv(DESKTOP_NVIDIA);
  const ctx = makeCtx({gpuFaceBlindAtDefault: true, gpuHandsBlind: false});
  const {health, controller: c} = build(env, ctx, memoryStorage());
  await c.init();
  assert.equal(c.variantId("face"), "gpu");
  await play(c, (FACE_BLIND_MS + env.warmupMs) / 1000 + 6);
  assert.equal(c.variantId("face"), "gpu-low", "the GPU recipe at a lower threshold comes before the CPU face model");
  assert.ok(!ctx.created.some((x) => x.startsWith("face:CPU")), "the CPU face model was never built");
  assert.equal(health.sawFace(), true);
  // and once the face works, a later empty spell (the player left) never triggers a rebuild
  const before = ctx.created.length;
  for (let i = 0; i < 600; i++) { t += 33; health.run("face", {ok: true, found: false}); }
  await c.tick();
  assert.equal(ctx.created.length, before, "an empty spell after the face worked is the player leaving, not a failing model");
}

// 18. Known-bad rule is enforced even if a GPU hand model somehow runs (e.g. built before the rule matched): switched at once.
{
  const env = detectEnv(ANDROID_ADRENO);
  const ctx = makeCtx();
  const health = newHealth(env);
  const events = [];
  const gpuFirst = {face: FACE_VARIANTS.slice(), hands: HAND_VARIANTS.slice(), fromCache: {face: false, hands: false}, ignored: []};
  const c = createDetectorController({ctx, env, ladders: gpuFirst, health, cache: createRecipeCache(memoryStorage()), frameFor: pass, now: clock, onEvent: (type, d) => events.push([type, d])});
  await c.init();
  assert.equal(c.variantId("hands"), "gpu");
  await c.tick();
  assert.equal(c.variantId("hands"), "cpu", "known-bad: switched immediately, no waiting for blindness");
  assert.ok(ids(events, "detector variant").some((d) => /gpu-hand-adreno/.test(d.why)), "the rule that matched is logged");
}

// 19. Expressions (blendshapes) are OPT-IN: off by default; turned on only after the plain face is healthy; a stall switches them off for good.
{
  const env = detectEnv(IPHONE_SAFARI);
  const store = memoryStorage();
  const ctx = makeCtx({gpuHandsBlind: false, blend: "stall"});
  const {health, events, controller: c} = build(env, ctx, store);
  await c.init();
  assert.ok(!ctx.created.some((x) => x.includes("+blend")), "no blendshape model by default");
  c.setExpressions(true);   // a game that needs expressions (wow, wink...) is selected before any face was seen
  await c.tick();
  assert.equal(c.expressions().on, false, "not switched on while the plain face has not been seen");
  await play(c, 1);
  assert.ok(ids(events, "detector variant").some((d) => d.to === "gpu-blend"), "switched on once the plain face was healthy");
  assert.equal(health.sawFace(), true);
  await play(c, 3);   // the blendshape model stalls (5 s per call)
  assert.equal(c.expressions().on, false, "the watchdog switched the stalled layer off");
  assert.equal(c.expressions().blocked, true);
  assert.equal(c.variantId("face"), "gpu", "back on the plain face model");
  assert.ok(ids(events, "detector expressions disabled").length === 1);
  assert.equal(createRecipeCache(store).load(env).blend, "blocked", "remembered for this device");
  c.setExpressions(true); await play(c, 3);
  assert.equal(c.expressions().on, false, "never retried once it stalled");
  // the next launch knows
  const second = build(env, makeCtx({gpuHandsBlind: false}), store);
  await second.controller.init();
  assert.equal(second.controller.expressions().blocked, true);
}
{
  // throwing layer: switched off after two strikes; a healthy layer stays on and is switched back off when the game no longer needs it
  const env = detectEnv(DESKTOP_NVIDIA);
  const ctx = makeCtx({gpuHandsBlind: false, blend: "throw"});
  const {controller: c} = build(env, ctx, memoryStorage());
  await c.init(); c.setExpressions(true);
  await play(c, 2); await play(c, 5);
  assert.equal(c.expressions().blocked, true, "a throwing expressions layer is blocked");
  assert.equal(c.variantId("face"), "gpu");

  const ctx2 = makeCtx({gpuHandsBlind: false, blend: "ok"});
  const good = build(env, ctx2, memoryStorage());
  await good.controller.init(); good.controller.setExpressions(true);
  await play(good.controller, 2);
  assert.equal(good.controller.expressions().on, true);
  await play(good.controller, BLEND_WATCHDOG_MS / 1000 + 4);
  assert.equal(good.controller.expressions().on, true, "a healthy expressions layer stays on");
  good.controller.setExpressions(false);
  await play(good.controller, 2);
  assert.equal(good.controller.expressions().on, false, "switched back to the plain model when the game does not need expressions");
  assert.equal(good.controller.expressions().blocked, false);
}

// 20. The Hand test winner: first in ladder order that works nearly as well as the best; tiny samples and the opt-in layer never win.
{
  const row = (id, frames, withHit, extra = {}) => ({id, created: true, frames, withHit, ...extra});
  // Android Adreno 830 (measured)
  assert.equal(pickWinner([row("gpu", 54, 53), row("gpu-low", 54, 52), row("cpu", 59, 0)]).id, "gpu");
  assert.equal(pickWinner([row("cpu", 71, 71), row("cpu-low", 75, 75), row("cpu-canvas", 54, 54), row("gpu", 82, 0), row("gpu-low", 82, 0), row("gpu-canvas", 81, 0)]).id, "cpu");
  // iPhone (measured): the GPU hand model sampled 1 frame at first: not evidence; gpu-low 46/46 is the first real winner
  assert.equal(pickWinner([row("gpu", 1, 1), row("gpu-low", 46, 46), row("cpu", 40, 40), row("cpu-low", 40, 40), row("gpu-canvas", 33, 33), row("cpu-canvas", 36, 36)]).id, "gpu-low");
  // iPhone face: blendshapes stalled (0/1) and is opt-in anyway; gpu 44/44 wins over the CPU 58/58
  assert.equal(pickWinner([row("gpu", 44, 44), row("gpu-low", 40, 40), row("cpu", 58, 58), row("gpu-blend", 1, 0, {optIn: true})]).id, "gpu");
  assert.equal(pickWinner([row("gpu", 30, 30), row("gpu-blend", 60, 60, {optIn: true})]).id, "gpu", "the opt-in layer is never the winner");
  assert.equal(pickWinner([row("gpu", 82, 0), row("gpu-low", 81, 0)]), null);
  assert.equal(pickWinner([row("gpu", 80, 30), row("cpu", 80, 79)]).id, "cpu", "a much better recipe beats an earlier mediocre one");
  assert.ok(FOUND_FRAMES_TO_REMEMBER >= 2 && MIN_WINNER_FRAMES >= 5);
}

// 21. PRE-WARM: the first (slow) inference of every model is paid on a throwaway frame during init, before any game frame, and never reaches health.
{
  const env = detectEnv(IPHONE_SAFARI);
  const ctx = makeCtx({gpuHandsBlind: false, firstCallMs: 9000});
  const {health, events, controller: c} = build(env, ctx, memoryStorage(), {warmFrame: () => ({blank: true})});
  const before = t;
  await c.init();
  assert.ok(t - before >= 18000, "init paid both models' 9 s first inference up front");
  assert.deepEqual(ids(events, "detector warmed").map((d) => d.model).sort(), ["face", "hands"]);
  assert.equal(health.summary().face.runs, 0, "the throwaway frame is not a health sample (can't count as blind or found)");
  const mark = t;
  await play(c, 1);
  assert.ok(t - mark < 2000, "the first real frames are steady-state: nothing slow is left to pay");
  assert.equal(ids(events, "detector slow").length, 0);
  // a rebuilt model (self-healing step) is warmed before it replaces the old one
  const desktop = build(detectEnv(DESKTOP_NVIDIA), makeCtx({firstCallMs: 7000}), memoryStorage(), {warmFrame: () => ({blank: true})});
  await desktop.controller.init(); await play(desktop.controller, 72);
  assert.equal(desktop.controller.variantId("hands"), "cpu");
  assert.ok(ids(desktop.events, "detector warmed").filter((d) => d.model === "hands").length >= 2, "the rebuilt hand model was warmed too");
  // no warm frame available (no DOM, no video): skipped quietly
  const none = build(detectEnv(DESKTOP_NVIDIA), makeCtx(), memoryStorage(), {warmFrame: () => null});
  await none.controller.init();
  assert.equal(ids(none.events, "detector warmed").length, 0);
}

// 22. The diag variant test warms every variant up before timing, so the FIRST one is not penalised for compiling shaders.
{
  let clock4 = 0;
  const slowFirst = new Set();
  const ctx = {
    files: {}, source: {}, modelBase: (key, path, delegate) => ({delegate}),
    vision: {HandLandmarker: {createFromOptions: async () => {
      let calls = 0;
      return {detectForVideo: () => { calls++; if (calls === 1) clock4 += 9000; return {landmarks: [[{x: 0, y: 0}]]}; }, close() {}};
    }}},
  };
  const report = await runHandTest({ctx, video: {readyState: 4, videoWidth: 640, videoHeight: 480}, seconds: 3, variants: HAND_VARIANTS.filter((v) => v.feed !== "canvas"), now: () => clock4, nextFrame: async () => { clock4 += 100; }});
  assert.ok(report.rows.every((r) => r.warmMs >= 9000), "the slow first inference was measured as warm-up");
  assert.ok(report.rows.every((r) => r.frames >= 25 && r.withHit === r.frames), "and did not eat into the timed window");
  assert.equal(report.winner, "gpu", "the first variant wins on merit, not on order");
}
console.log("detect health ok");

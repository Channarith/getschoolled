// ONE place that builds the MediaPipe face and hand detectors, used by the games (app.js) AND by /diag/vision,
// so the diagnostic page is a faithful regression harness for the game.
//
// A "variant" is a complete recipe: delegate (GPU/CPU), confidence thresholds, face blendshapes on/off, and how frames are fed
// (the video element itself, or a canvas copy of it). Phones differ: a recipe that works on one GPU returns nothing on another
// (a known Adreno failure class for the hand model). The game starts with variant 0 and walks down the ladder only when a model
// stays blind (see detect_health.js); /diag/vision's hand test tries every variant and reports which one sees a hand.
export const FACE_VARIANTS = [
  {id: "gpu", delegate: "GPU", blendshapes: false, conf: 0.5, feed: "video"},       // plain face landmarks: what almost every game needs
  {id: "gpu-low", delegate: "GPU", blendshapes: false, conf: 0.3, feed: "video"},    // a far or small face
  {id: "cpu", delegate: "CPU", blendshapes: false, conf: 0.5, feed: "video"},        // last resort (it does not work on every GPU class)
];
// Expression blendshapes are an OPT-IN layer, never part of the default ladder: on iPhone (Safari, iOS 18.7) the GPU recipe with
// blendshapes stalled (1 frame in ~9 s) while the plain one ran 44/44. Only the games below read expressions, and the layer is only
// switched on once the plain face model is healthy, with a watchdog that turns it off again (see createDetectorController).
export const FACE_BLEND_VARIANT = {id: "gpu-blend", delegate: "GPU", blendshapes: true, conf: 0.5, feed: "video", optIn: true};
export const EXPRESSION_GAMES = new Set(["popcorn", "wow", "wink", "blow-kiss", "oh-behave"]);
// Hands start at confidence 0.4 everywhere: at 0.5 the iPhone GPU model returned almost nothing on its first rung, while 0.3 worked.
export const HAND_VARIANTS = [
  {id: "gpu", delegate: "GPU", conf: 0.4, feed: "video"},
  {id: "gpu-low", delegate: "GPU", conf: 0.3, feed: "video"},
  {id: "cpu", delegate: "CPU", conf: 0.4, feed: "video"},
  {id: "cpu-low", delegate: "CPU", conf: 0.3, feed: "video"},
  {id: "gpu-canvas", delegate: "GPU", conf: 0.4, feed: "canvas"},
  {id: "cpu-canvas", delegate: "CPU", conf: 0.3, feed: "canvas"},
];

export const variantOf = (list, index) => list[Math.max(0, Math.min(list.length - 1, Number(index) || 0))];

// ctx = {vision, files, modelBase, source}: the imported library, its wasm files, and a (key, path, delegate) -> baseOptions helper.
export function faceOptions(ctx, variant) {
  return {
    baseOptions: ctx.modelBase("face", ctx.source.face, variant.delegate),
    runningMode: "VIDEO", numFaces: 1, outputFaceBlendshapes: Boolean(variant.blendshapes),
    minFaceDetectionConfidence: variant.conf, minFacePresenceConfidence: variant.conf, minTrackingConfidence: variant.conf,
  };
}
export function handOptions(ctx, variant) {
  return {
    baseOptions: ctx.modelBase("hand", ctx.source.hand, variant.delegate),
    runningMode: "VIDEO", numHands: 2,
    minHandDetectionConfidence: variant.conf, minHandPresenceConfidence: variant.conf, minTrackingConfidence: variant.conf,
  };
}
export const createFace = (ctx, variant) => ctx.vision.FaceLandmarker.createFromOptions(ctx.files, faceOptions(ctx, variant));
export const createHands = (ctx, variant) => ctx.vision.HandLandmarker.createFromOptions(ctx.files, handOptions(ctx, variant));

// What to hand to detectForVideo: the video element, or a canvas copy (some GPUs only read frames drawn through a canvas).
export function createFeeder() {
  let canvas = null;
  let g2d = null;
  return function frameFor(video, variant) {
    if (!variant || variant.feed !== "canvas") return video;
    const w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) return video;
    if (!canvas) { canvas = document.createElement("canvas"); g2d = canvas.getContext("2d", {willReadFrequently: false}); }
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    g2d.drawImage(video, 0, 0, w, h);
    return canvas;
  };
}

// ---- This device: what it is, which known-bad rules apply, and the per-device recipe cache -----------------------------------
// Proven on a real phone (Android, Chrome 156, Adreno 830, /diag/vision Hand test, two identical runs): the GPU hand landmarker returns
// NOTHING on that GPU (0/82 frames, also at confidence 0.3 and with a canvas feed) while the CPU hand landmarker sees both hands in
// 71/71 frames; the GPU face landmarker works (52/57, 53/54) and the CPU face landmarker does not (0/59).
// NOT known-bad (proven on an iPhone, Safari, iOS 18.7, Apple GPU): hands GPU works at confidence 0.3 (46/46) and the CPU works too,
// and the CPU face works (58/58). So the rule below is limited to Qualcomm Adreno and nothing else is forced.
export const KNOWN_BAD_RULES = [
  {id: "gpu-hand-adreno", model: "hands", delegate: "GPU", why: "GPU hand landmarker returns nothing on Qualcomm Adreno (proven: Adreno 830, Chrome 156)",
    test: (env) => /adreno/i.test(env.renderer || "")},
];

const tail = (text, n) => String(text || "").slice(0, n);
export function hashText(text) {   // FNV-1a, 32 bit: a short stable key, not a secret
  let h = 0x811c9dc5;
  const input = String(text || "");
  for (let i = 0; i < input.length; i++) { h ^= input.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16).padStart(8, "0");
}
function readRenderer() {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (!gl) return "";
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const text = String((ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) || "");
    gl.getExtension("WEBGL_lose_context")?.loseContext();   // do not keep a spare graphics context alive on a phone
    return text;
  } catch (_) { return ""; }
}
// overrides: {ua, renderer, mobile} for tests; otherwise read from the browser.
export function detectEnv(overrides = {}) {
  const nav = typeof navigator !== "undefined" ? navigator : {};
  const ua = String(overrides.ua ?? nav.userAgent ?? "");
  const renderer = String(overrides.renderer ?? readRenderer());
  const android = /Android/i.test(ua);
  const ios = /iPhone|iPad|iPod/i.test(ua);
  const mobile = overrides.mobile ?? (android || ios || /Mobile/i.test(ua) || Boolean(nav.userAgentData?.mobile));
  const found = ua.match(/(Chrome|CriOS|EdgA|SamsungBrowser)\/(\d+)/);
  const chromium = Boolean(found) && !ios;   // Chrome on iOS is WebKit underneath: it behaves like Safari
  const browser = found ? `${found[1]}/${found[2]}` : tail(ua, 40);   // the major version: a browser update re-learns the recipe
  const androidChromium = android && chromium;
  const env = {ua: tail(ua, 160), renderer, android, ios, mobile, chromium, androidChromium, browser, rules: [], knownBad: {face: {}, hands: {}},
    // The first inference after a model is created can take seconds on iOS (asset load, shader compile): blind timers wait this long extra.
    warmupMs: ios ? 12000 : 2000};
  if (androidChromium) env.rules.push("android-chromium: hands start on the CPU (a default, not a known-bad)");
  for (const rule of KNOWN_BAD_RULES) {
    if (!rule.test(env)) continue;
    env.rules.push(rule.id);
    env.knownBad[rule.model][rule.delegate] = rule.id;
  }
  env.handsCpuFirst = androidChromium || Boolean(env.knownBad.hands.GPU);
  env.key = hashText(`${renderer}|${browser}`);
  env.rendererKey = hashText(renderer);
  return env;
}

// Desktop keeps the defaults. On mobile Chromium, and anywhere a known-bad rule matches, the hand ladder starts on the CPU and the GPU
// hand variants are last (a last resort, never the first thing tried). The face ladder is always GPU with blendshapes -> GPU without
// blendshapes -> CPU: CPU face is only reached when both GPU recipes stayed blind or threw.
// cache = {face: id, hands: id} of recipes that were proven on THIS device; a proven recipe goes first (unless a known-bad rule forbids it).
export function buildLadders(env, cache = {}) {
  const face = FACE_VARIANTS.slice();
  let hands = HAND_VARIANTS.slice();
  if (env.handsCpuFirst) hands = [...hands.filter((v) => v.delegate === "CPU"), ...hands.filter((v) => v.delegate !== "CPU")];
  const fromCache = {face: false, hands: false};
  const ignored = [];
  const lists = {face, hands};
  for (const name of ["face", "hands"]) {
    const id = cache?.[name];
    if (!id) continue;
    const list = lists[name];
    const at = list.findIndex((v) => v.id === id);
    if (at < 0) { ignored.push({model: name, id, why: "unknown recipe"}); continue; }
    const rule = env.knownBad[name]?.[list[at].delegate];
    if (rule) { ignored.push({model: name, id, why: `known-bad rule ${rule}`}); continue; }
    if (at > 0) lists[name] = [list[at], ...list.slice(0, at), ...list.slice(at + 1)];
    fromCache[name] = true;
  }
  return {face: lists.face, hands: lists.hands, fromCache, ignored};
}

export function memoryStorage() {
  const data = new Map();
  return {getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => { data.set(k, String(v)); }, removeItem: (k) => { data.delete(k); }};
}
const CACHE_KEY = "gs_detector_recipes_v1";
const CACHE_MAX = 6;
// Per-device recipe cache in localStorage: {entries: {[key]: {rh, browser, face?: {id, at}, hands?: {id, at}}}}.
// key = hash(WebGL renderer | browser major version). A different phone, or a browser update, is a different key, so it re-learns.
export function createRecipeCache(storage, now = () => Date.now()) {
  let store = storage;
  const read = () => {
    try { const parsed = JSON.parse(store.getItem(CACHE_KEY) || "null"); return parsed && typeof parsed.entries === "object" ? parsed : {entries: {}}; }
    catch (_) { return {entries: {}}; }
  };
  const write = (data) => {
    try { store.setItem(CACHE_KEY, JSON.stringify(data)); }
    catch (_) { store = memoryStorage(); try { store.setItem(CACHE_KEY, JSON.stringify(data)); } catch (__) { /* nothing to do */ } }
  };
  return {
    load(env) {
      const entry = read().entries[env.key];
      return {face: entry?.face?.id || "", hands: entry?.hands?.id || "", blend: entry?.blend?.id || ""};
    },
    save(env, name, id) {
      const data = read();
      // A browser update on the same GPU makes the old recipe stale: drop entries for the same renderer under another version.
      for (const [key, entry] of Object.entries(data.entries)) if (entry.rh === env.rendererKey && key !== env.key) delete data.entries[key];
      const entry = data.entries[env.key] || (data.entries[env.key] = {rh: env.rendererKey, browser: env.browser});
      entry[name] = {id, at: now()};
      const keys = Object.keys(data.entries);
      if (keys.length > CACHE_MAX) for (const key of keys.sort((a, b) => latest(data.entries[a]) - latest(data.entries[b])).slice(0, keys.length - CACHE_MAX)) delete data.entries[key];
      write(data);
    },
    drop(env, name) {
      const data = read();
      const entry = data.entries[env.key];
      if (!entry || !entry[name]) return false;
      delete entry[name];
      if (!entry.face && !entry.hands && !entry.blend) delete data.entries[env.key];
      write(data);
      return true;
    },
    clear() { try { store.removeItem(CACHE_KEY); } catch (_) { /* nothing to do */ } },
  };
}
const latest = (entry) => Math.max(entry?.face?.at || 0, entry?.hands?.at || 0, entry?.blend?.at || 0);

// ---- The controller: builds the models from the ladder, runs them per frame, and heals itself -----------------------------------
// It never needs the user: a model that throws or stays blind walks down its ladder (detect_health.js decides when), the recipe that
// first really sees someone is remembered for this device, and a remembered recipe that goes blind is forgotten.
export const FOUND_FRAMES_TO_REMEMBER = 3;
export const SLOW_CALL_MS = 1500;          // one inference slower than this is "slow" (after the model's warm-up calls)
export const WARMUP_CALLS = 3;             // the first calls after a model is built may take seconds (iOS): never judged slow
export const SLOW_CALLS_TO_STEP = 3;       // this many slow calls in a row count as the model failing
export const BLEND_WATCHDOG_MS = 6000;     // expressions layer: no frames this long after it was switched on -> switched off for good
export const BLEND_SLOW_STRIKES = 2;       // ...or this many slow/throwing calls
function blankFrame() {
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  canvas.width = 160; canvas.height = 120;
  const g = canvas.getContext("2d");
  if (g) { g.fillStyle = "#808080"; g.fillRect(0, 0, 160, 120); }
  return canvas;
}
export function createDetectorController({ctx, env, ladders, health, cache, frameFor = createFeeder(), onModel = () => {}, onEvent = () => {}, warmFrame = blankFrame, now = () => (typeof performance !== "undefined" ? performance.now() : Date.now())}) {
  const make = {face: (variant) => createFace(ctx, variant), hands: (variant) => createHands(ctx, variant)};
  const models = {face: null, hands: null};
  const index = {face: 0, hands: 0};
  const cached = {face: false, hands: false};
  const rebuilding = {face: false, hands: false};
  const calls = {face: 0, hands: 0};            // calls since the model was (re)built
  const slow = {face: 0, hands: 0};             // consecutive slow calls
  const foundOnVariant = {};
  const remembered = {};
  let errorsLogged = 0;
  let lastVideo = null;

  // The first inference of a new model compiles shaders and builds its graph (7-9 s on an iPhone). Pay that now, on a throwaway frame,
  // so the first real frame is already steady-state. It never reaches health, so it can neither count as blind nor as a find.
  function warm(name, model, variant) {
    const source = lastVideo && lastVideo.readyState >= 2 && lastVideo.videoWidth ? frameFor(lastVideo, variant) : warmFrame();
    if (!source) return;
    const t0 = now();
    try { model.detectForVideo(source, 1); } catch (_) { /* a throwaway frame may fail; real frames are judged by health */ }
    onEvent("detector warmed", {model: name, variant: variant.id, ms: Math.round(now() - t0)});
  }
  // Expressions (blendshapes) are an opt-in layer on the face model: wanted by a game, allowed only while the plain face is healthy,
  // and switched off for good (and remembered per device) if it stalls.
  const expr = {wanted: false, on: false, since: 0, frames: 0, strikes: 0, blocked: false};

  async function init() {
    expr.blocked = cache?.load(env)?.blend === "blocked";
    onEvent("detector env", {renderer: tail(env.renderer, 80), browser: env.browser, mobile: env.mobile, ios: env.ios, rules: env.rules, cacheUsed: ladders.fromCache, cacheIgnored: ladders.ignored, expressionsBlocked: expr.blocked});
    for (const name of ["face", "hands"]) {
      const run = await createFirstWorking(ladders[name], make[name], {note: (variant, error) => onEvent("detector create failed", {model: name, variant: variant.id, message: String(error?.message || error).slice(0, 120)})});
      if (run.model) {
        warm(name, run.model, run.variant);
        models[name] = run.model; index[name] = run.index; calls[name] = 0; slow[name] = 0;
        cached[name] = ladders.fromCache[name] && run.index === 0;
        health.register(name, run.variant.delegate, run.index, run.variant.id, {fromCache: cached[name]});
        onModel(name, run.model);
        onEvent("detector ready", {model: name, variant: run.variant.id, delegate: run.variant.delegate, fromCache: cached[name]});
      } else {
        health.fail(name, run.errors.slice(-1)[0] || "model unavailable");
        onEvent("detector load failed", {model: name, reason: run.errors.slice(-1)[0] || ""});
      }
    }
  }

  const variantNow = (name) => (name === "face" && expr.on ? FACE_BLEND_VARIANT : variantOf(ladders[name], index[name]));
  function remember(name) {
    const variant = variantNow(name);
    if (variant.optIn) return;   // the expressions layer is never "the recipe": the plain one is what gets remembered
    const tag = `${name}:${variant.id}`;
    foundOnVariant[tag] = (foundOnVariant[tag] || 0) + 1;
    if (foundOnVariant[tag] === 1) onEvent("detector found", {model: name, variant: variant.id, delegate: variant.delegate, tried: health.summary()[name]?.tried});
    if (foundOnVariant[tag] >= FOUND_FRAMES_TO_REMEMBER && !remembered[tag]) {
      remembered[tag] = true;
      cache?.save(env, name, variant.id);
      onEvent("detector remembered", {model: name, variant: variant.id});
    }
  }

  // One detection on one frame. Returns the raw result, or null (no model, or it threw: recorded in health).
  function detect(name, video, ts) {
    const model = models[name];
    if (!model) return null;
    lastVideo = video;
    const t0 = now();
    try {
      const result = model.detectForVideo(frameFor(video, variantNow(name)), ts);
      const dt = now() - t0;
      calls[name]++;
      const found = (name === "face" ? result?.faceLandmarks?.length : result?.landmarks?.length) > 0;
      const overlay = name === "face" && expr.on;
      // Warm-up calls are exempt. After that, a model that keeps taking seconds per frame is failing, even though it "works".
      if (calls[name] > WARMUP_CALLS && dt > SLOW_CALL_MS) {
        slow[name]++;
        if (overlay) expr.strikes++;
        if (slow[name] >= SLOW_CALLS_TO_STEP) { health.run(name, {ok: false, error: `slow inference ${Math.round(dt)} ms`}); }
        else health.run(name, {ok: true, found});
        if (errorsLogged++ < 6) onEvent("detector slow", {model: name, variant: variantNow(name).id, ms: Math.round(dt), calls: calls[name]});
      } else {
        slow[name] = 0;
        health.run(name, {ok: true, found});
      }
      if (overlay) expr.frames++;
      if (found) remember(name);
      return result;
    } catch (error) {
      calls[name]++;
      health.run(name, {ok: false, error: error?.message || error});
      if (name === "face" && expr.on) expr.strikes++;
      if (errorsLogged++ < 6) onEvent("detector error", {model: name, variant: variantNow(name).id, message: String(error?.message || error).slice(0, 140)});
      return null;
    }
  }

  async function rebuild(name, to, why, {variant: forced = null, overlay = false} = {}) {
    if (rebuilding[name]) return false;
    rebuilding[name] = true;
    const variant = forced || variantOf(ladders[name], to);
    if (cached[name] && !overlay) {
      cache?.drop(env, name);
      onEvent("detector forgot remembered recipe", {model: name, variant: variantNow(name).id, why});
    }
    onEvent("detector variant", {model: name, from: variantNow(name).id, to: variant.id, why});
    try {
      const next = await make[name](variant);
      warm(name, next, variant);
      const old = models[name];
      models[name] = next; index[name] = to; cached[name] = false; calls[name] = 0; slow[name] = 0;
      try { old?.close?.(); } catch (_) { /* already closed */ }
      health.markVariant(name, to, variant.id, variant.delegate);
      onModel(name, next);
      onEvent("detector variant ready", {model: name, variant: variant.id});
      return true;
    } catch (error) {
      index[name] = to; cached[name] = false;
      health.markVariant(name, to, variant.id, variant.delegate);   // skip it: the next tick tries the following variant
      onEvent("detector variant failed", {model: name, variant: variant.id, message: String(error?.message || error).slice(0, 140)});
      return false;
    } finally { rebuilding[name] = false; }
  }

  // A game asks for expressions (or stops needing them). Nothing happens until tick() sees the plain face model is healthy.
  function setExpressions(wanted) { expr.wanted = Boolean(wanted); }
  async function switchExpressions(on, why) {
    if (expr.on === on) return;
    const was = expr.on;
    expr.on = on;   // variantNow() already reports the new recipe while it builds
    const ok = await rebuild("face", index.face, why, {variant: on ? FACE_BLEND_VARIANT : variantOf(ladders.face, index.face), overlay: true});
    if (!ok) { expr.on = was; if (on) expr.blocked = true; }
    else { expr.since = now(); expr.frames = 0; expr.strikes = 0; }
  }
  async function blockExpressions(why) {
    expr.blocked = true;
    cache?.save(env, "blend", "blocked");
    onEvent("detector expressions disabled", {why});
    await switchExpressions(false, `expressions off: ${why}`);
  }

  // Called on a slow timer. Rebuilds a model when detect_health says so, or at once when the model in use matches a known-bad rule.
  async function tick() {
    for (const name of ["face", "hands"]) {
      if (!models[name] || rebuilding[name]) continue;
      if (name === "face" && expr.on) continue;   // the expressions layer has its own watchdog below
      const variant = variantNow(name);
      const rule = env.knownBad[name]?.[variant.delegate];
      if (rule) {
        const safe = ladders[name].findIndex((v) => !env.knownBad[name]?.[v.delegate]);
        if (safe >= 0 && safe !== index[name]) { await rebuild(name, safe, `known-bad rule ${rule}`); continue; }
      }
      const next = health.fallbackWanted(name);
      if (next >= 0) await rebuild(name, next, "blind or throwing");
    }
    if (rebuilding.face) return;
    if (expr.on) {
      // Watchdog: expressions must keep producing frames, quickly. Otherwise switch them off for good on this device.
      if (expr.strikes >= BLEND_SLOW_STRIKES) await blockExpressions("slow or throwing");
      else if (now() - expr.since >= BLEND_WATCHDOG_MS && expr.frames < 5) await blockExpressions(`no frames in ${BLEND_WATCHDOG_MS} ms`);
      else if (!expr.wanted) await switchExpressions(false, "no longer needed");
    } else if (expr.wanted && !expr.blocked && models.face && health.presenceAllowed() && health.healthy("face")) {
      await switchExpressions(true, "a game uses expressions");
    }
  }
  return {init, detect, tick, setExpressions, models: () => ({...models}), indexOf: (name) => index[name], variantId: (name) => (models[name] ? variantNow(name).id : ""),
    isCached: (name) => cached[name], rebuilding: () => rebuilding.face || rebuilding.hands, expressions: () => ({...expr})};
}

// Run the ladder for one model: try each variant in order until one creates. Returns {model, variant, index, errors}.
export async function createFirstWorking(list, make, {note = () => {}, from = 0} = {}) {
  const errors = [];
  for (let i = from; i < list.length; i++) {
    try {
      const model = await make(list[i]);
      return {model, variant: list[i], index: i, errors};
    } catch (error) {
      errors.push(`${list[i].id}: ${String(error?.message || error).slice(0, 120)}`);
      note(list[i], error);
      // GPU and CPU variants differ only in delegate/thresholds: once a GPU create fails, skip the other GPU variants of this model.
      while (i + 1 < list.length && list[i].delegate === "GPU" && list[i + 1].delegate === "GPU") i++;
    }
  }
  return {model: null, variant: null, index: -1, errors};
}

// The /diag/vision variant tests: for each variant, build the model, feed it frames for `seconds`, count frames that saw a face/hand.
// kind = "hands" | "face". nextFrame(video) must resolve on the next real camera frame.
const WARMUP_FRAMES = 3;
export async function runVariantTest({kind = "hands", ctx, video, seconds = 3, variants, onProgress = () => {}, now = () => performance.now(), nextFrame}) {
  const list = variants || (kind === "face" ? FACE_VARIANTS : HAND_VARIANTS);
  const make = kind === "face" ? createFace : createHands;
  const countOf = (r) => (kind === "face" ? (r.faceLandmarks?.length || 0) : (r.landmarks?.length || 0));
  const frameFor = createFeeder();
  const rows = [];
  let lastTs = 0;
  for (const variant of list) {
    const row = {kind, id: variant.id, optIn: Boolean(variant.optIn), delegate: variant.delegate, conf: variant.conf, feed: variant.feed, blendshapes: variant.blendshapes, created: false, warmMs: 0, frames: 0, withHit: 0, max: 0, ms: 0, error: ""};
    let model = null;
    try {
      const t0 = now();
      model = await make(ctx, variant);
      row.ms = Math.round(now() - t0); row.created = true;
    } catch (error) { row.error = String(error?.message || error).slice(0, 140); }
    if (model) {
      // Warm-up pass BEFORE timing: the first inference of any new model compiles shaders (7-9 s on an iPhone), so whichever variant
      // ran first used to look "stalled". Throwaway frames, not counted, so order cannot confound the result.
      for (let i = 0; i < WARMUP_FRAMES; i++) {
        await nextFrame(video);
        if (video.readyState < 2) continue;
        const w0 = now();
        const ts = Math.max(lastTs + 1, w0);
        lastTs = ts;
        try { model.detectForVideo(frameFor(video, variant), ts); } catch (_) { /* judged on the timed frames */ }
        if (i === 0) row.warmMs = Math.round(now() - w0);
      }
      const end = now() + seconds * 1000;
      while (now() < end) {
        await nextFrame(video);
        if (video.readyState < 2) continue;
        const ts = Math.max(lastTs + 1, now());
        lastTs = ts;
        row.frames++;
        try {
          const n = countOf(model.detectForVideo(frameFor(video, variant), ts));
          if (n) row.withHit++;
          row.max = Math.max(row.max, n);
        } catch (error) { row.error = String(error?.message || error).slice(0, 140); break; }
      }
      try { model.close?.(); } catch (_) { /* closed */ }
    }
    rows.push(row);
    onProgress(row, rows);
  }
  const best = pickWinner(rows);
  return {kind, rows, winner: best ? best.id : "", saw: Boolean(best)};
}
export const runHandTest = (options) => runVariantTest({...options, kind: "hands"});

// The recipe to keep: the FIRST one (in ladder order, which is also the order of preference) that works nearly as well as the best,
// so face gpu-blend (52/57 frames) is kept over gpu (53/54), because the games need the expression blendshapes.
export const WINNER_SLACK = 0.85;
export const MIN_WINNER_FRAMES = 10;   // "1 of 1 frames" is a slow warm-up, not evidence (an iPhone GPU hand model sampled 1 frame at 0.5)
export function pickWinner(rows) {
  const rate = (r) => r.withHit / Math.max(1, r.frames);
  const working = rows.filter((r) => r.created && !r.optIn && r.frames >= MIN_WINNER_FRAMES && r.withHit >= 1);
  if (!working.length) return null;
  const top = Math.max(...working.map(rate));
  return working.find((r) => rate(r) >= top * WINNER_SLACK) || null;
}

// One throwaway frame through a fresh landmarker/segmenter (any model with detectForVideo/segmentForVideo) so shaders compile before the game needs it.
export function warmModel(model, source, kind = "detect") {
  const t0 = typeof performance !== "undefined" ? performance.now() : 0;
  try { const result = kind === "segment" ? model.segmentForVideo(source, 1) : model.detectForVideo(source, 1); result?.close?.(); } catch (_) { /* throwaway */ }
  return (typeof performance !== "undefined" ? performance.now() : 0) - t0;
}
export {blankFrame};

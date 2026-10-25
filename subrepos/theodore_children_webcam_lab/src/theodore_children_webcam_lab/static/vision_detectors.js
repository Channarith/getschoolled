// ONE place that builds the MediaPipe face and hand detectors, used by the games (app.js) AND by /diag/vision,
// so the diagnostic page is a faithful regression harness for the game.
//
// A "variant" is a complete recipe: delegate (GPU/CPU), confidence thresholds, face blendshapes on/off, and how frames are fed
// (the video element itself, or a canvas copy of it). Phones differ: a recipe that works on one GPU returns nothing on another
// (a known Adreno failure class for the hand model). The game starts with variant 0 and walks down the ladder only when a model
// stays blind (see detect_health.js); /diag/vision's hand test tries every variant and reports which one sees a hand.
export const FACE_VARIANTS = [
  {id: "gpu-blend", delegate: "GPU", blendshapes: true, conf: 0.5, feed: "video"},   // what the games need for expressions
  {id: "gpu", delegate: "GPU", blendshapes: false, conf: 0.5, feed: "video"},        // what /diag/vision used when it worked
  {id: "cpu", delegate: "CPU", blendshapes: false, conf: 0.5, feed: "video"},
];
export const HAND_VARIANTS = [
  {id: "gpu", delegate: "GPU", conf: 0.5, feed: "video"},
  {id: "cpu", delegate: "CPU", conf: 0.5, feed: "video"},
  {id: "cpu-low", delegate: "CPU", conf: 0.3, feed: "video"},
  {id: "gpu-low", delegate: "GPU", conf: 0.3, feed: "video"},
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
export async function runVariantTest({kind = "hands", ctx, video, seconds = 3, variants, onProgress = () => {}, now = () => performance.now(), nextFrame}) {
  const list = variants || (kind === "face" ? FACE_VARIANTS : HAND_VARIANTS);
  const make = kind === "face" ? createFace : createHands;
  const countOf = (r) => (kind === "face" ? (r.faceLandmarks?.length || 0) : (r.landmarks?.length || 0));
  const frameFor = createFeeder();
  const rows = [];
  let lastTs = 0;
  for (const variant of list) {
    const row = {kind, id: variant.id, delegate: variant.delegate, conf: variant.conf, feed: variant.feed, blendshapes: variant.blendshapes, created: false, frames: 0, withHit: 0, max: 0, ms: 0, error: ""};
    let model = null;
    try {
      const t0 = now();
      model = await make(ctx, variant);
      row.ms = Math.round(now() - t0); row.created = true;
    } catch (error) { row.error = String(error?.message || error).slice(0, 140); }
    if (model) {
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
  const best = rows.filter((r) => r.withHit > 0).sort((a, b) => b.withHit / Math.max(1, b.frames) - a.withHit / Math.max(1, a.frames))[0] || null;
  return {kind, rows, winner: best ? best.id : "", saw: Boolean(best)};
}
export const runHandTest = (options) => runVariantTest({...options, kind: "hands"});

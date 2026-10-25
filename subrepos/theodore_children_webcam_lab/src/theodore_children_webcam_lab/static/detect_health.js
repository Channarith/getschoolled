// Tracks whether the phone's face/hand detectors really work, so a silent failure never pauses a lesson.
// Pure logic (no DOM): app.js feeds it one record per frame and asks what to do.
//
// Why it exists: on a real phone the models can load but return nothing (GPU delegate quirks, an Adreno failure class for the hand
// model), or fail to load at all. The old code then treated "no face seen" as "the child left the camera" and paused the game.
//
// Each model walks a LADDER of variants (see vision_detectors.js: delegate, thresholds, blendshapes, frame feed). It moves to the
// next variant only when the current one throws repeatedly or stays blind long enough to be suspicious.
export const ERRORS_BEFORE_NEXT = 3;          // consecutive frame exceptions before the next variant
export const FACE_BLIND_MS = 6000;            // a face model that never found a face in this long moves on
export const HANDS_AFTER_FACE_MS = 8000;      // hands are only judged blind once a face has been working this long (the player is there)
export const HANDS_BLIND_MS = 10000;          // ...and a hand model blind this long (while a person is in front) moves on
export const BLIND_MS_BEFORE_TOUCH = 12000;   // nothing found on the last variant either: play by touch (silently)
export const HEALTHY_WINDOW_MS = 2000;        // "running" means it produced a frame result without error this recently

export function createDetectHealth(options = {}) {
  const clock = options.now || (() => (typeof performance !== "undefined" ? performance.now() : Date.now()));
  const counts = {face: 1, hands: 1, ...(options.variants || {})};
  const models = {};
  let sawFace = false;
  let sawHand = false;
  let firstFaceAt = null;

  const model = (name) => (models[name] ||= {
    name, state: "idle", delegate: "", variant: 0, variantId: "", runs: 0, found: 0, errors: 0, consecutiveErrors: 0, lastError: "",
    runningSince: null, lastFoundAt: 0, lastRunAt: 0, reason: "", tried: [], foundByVariant: {},
  });

  function register(name, delegate, variant = 0, variantId = "") {
    const m = model(name);
    m.state = "ready"; m.delegate = delegate; m.variant = variant; m.variantId = variantId || String(variant);
    m.runningSince = null; m.consecutiveErrors = 0; m.reason = ""; m.lastFoundAt = 0;
    if (!m.tried.includes(m.variantId)) m.tried.push(m.variantId);
    return m;
  }
  function fail(name, reason) {
    const m = model(name);
    m.state = "failed"; m.reason = String(reason || "failed").slice(0, 160);
    return m;
  }
  // One frame. ok=false means the detector threw. found=true means it returned a face / hand.
  function run(name, {ok = true, found = false, error = ""} = {}) {
    const m = model(name);
    const now = clock();
    m.runs++;
    if (!ok) {
      m.errors++; m.consecutiveErrors++; m.lastError = String(error || "error").slice(0, 160);
      return m;
    }
    m.consecutiveErrors = 0;
    m.lastRunAt = now;
    if (m.runningSince === null) m.runningSince = now;
    if (found) {
      m.found++; m.lastFoundAt = now;
      m.foundByVariant[m.variantId] = (m.foundByVariant[m.variantId] || 0) + 1;
      if (name === "face") { sawFace = true; if (firstFaceAt === null) firstFaceAt = now; }
      if (name === "hands") sawHand = true;
    }
    return m;
  }

  // Index of the variant this model should be rebuilt with, or -1 to stay as it is.
  function fallbackWanted(name) {
    const m = model(name);
    const last = (counts[name] || 1) - 1;
    if (m.state !== "ready" || m.variant >= last) return -1;
    if (m.consecutiveErrors >= ERRORS_BEFORE_NEXT) return m.variant + 1;
    const blindFor = m.runningSince !== null ? clock() - Math.max(m.runningSince, m.lastFoundAt) : 0;
    if (name === "face") {
      if (!sawFace && m.found === 0 && blindFor >= FACE_BLIND_MS) return m.variant + 1;
    } else if (name === "hands") {
      // Only suspicious when a person is plainly there (the face works) and no hand was ever seen.
      const faceFor = firstFaceAt === null ? 0 : clock() - firstFaceAt;
      if (!sawHand && m.found === 0 && faceFor >= HANDS_AFTER_FACE_MS && blindFor >= HANDS_BLIND_MS) return m.variant + 1;
    }
    return -1;
  }
  function markVariant(name, variant, variantId, delegate) {
    const m = model(name);
    m.variant = variant; m.variantId = variantId || String(variant); m.delegate = delegate || m.delegate;
    m.runningSince = null; m.consecutiveErrors = 0; m.lastFoundAt = 0;
    if (!m.tried.includes(m.variantId)) m.tried.push(m.variantId);
    return m;
  }
  const healthy = (name) => {
    const m = model(name);
    return m.state === "ready" && m.consecutiveErrors === 0 && m.lastRunAt > 0 && clock() - m.lastRunAt <= HEALTHY_WINDOW_MS;
  };

  // "You left the camera" needs BOTH: the detector has seen this player before, and it is running healthily right now.
  // Absence only means something when the detector could have seen the person.
  function presenceAllowed() {
    return sawFace && healthy("face");
  }

  // '' when tracking looks fine or is still loading; otherwise why the game should quietly use screen touch.
  function touchFallback() {
    const face = model("face");
    const hands = model("hands");
    const anyReady = face.state === "ready" || hands.state === "ready";
    const anyLoading = face.state === "idle" || hands.state === "idle";
    if (sawFace || sawHand) return "";
    if (!anyReady && !anyLoading) return "no-model";
    for (const m of [face, hands]) {
      if (m.state !== "ready") continue;
      const last = (counts[m.name] || 1) - 1;
      if (m.consecutiveErrors >= ERRORS_BEFORE_NEXT && m.variant >= last) return "detector-errors";
    }
    const ready = [face, hands].filter((m) => m.state === "ready" && m.runningSince !== null);
    if (ready.length && ready.every((m) => m.variant >= (counts[m.name] || 1) - 1 && clock() - m.runningSince >= BLIND_MS_BEFORE_TOUCH)) {
      return "no-detections";
    }
    return "";
  }
  function loading() {
    return model("face").state === "idle" || model("hands").state === "idle";
  }
  function summary() {
    const out = {sawFace, sawHand};
    for (const [name, m] of Object.entries(models)) {
      out[name] = {
        state: m.state, delegate: m.delegate, variant: m.variantId, tried: m.tried.slice(), runs: m.runs, found: m.found, errors: m.errors,
        lastError: m.lastError, reason: m.reason, foundByVariant: {...m.foundByVariant},
      };
    }
    return out;
  }

  return {register, fail, run, fallbackWanted, markVariant, presenceAllowed, touchFallback, loading, healthy, summary,
    sawPerson: () => sawFace || sawHand, sawFace: () => sawFace, sawHand: () => sawHand};
}

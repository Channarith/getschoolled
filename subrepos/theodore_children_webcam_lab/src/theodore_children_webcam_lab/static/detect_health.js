// Tracks whether the phone's face/hand detectors really work, so a silent failure never pauses a lesson.
// Pure logic (no DOM): app.js feeds it one record per frame and asks what to do.
//
// Why it exists: on a real phone the models can load but return nothing (GPU delegate quirks), or fail to load at all.
// The old code then treated "no face seen" as "the child left the camera" and paused the game for good.
export const ERRORS_BEFORE_CPU = 3;        // consecutive frame exceptions on the GPU delegate before rebuilding on the CPU
export const BLIND_MS_BEFORE_CPU = 6000;   // a running GPU model that never found a person in this long gets a CPU rebuild
export const BLIND_MS_BEFORE_TOUCH = 12000; // nothing found on the CPU either: play with the screen instead (silently)

export function createDetectHealth(options = {}) {
  const clock = options.now || (() => (typeof performance !== "undefined" ? performance.now() : Date.now()));
  const models = {};
  let sawFace = false;
  let sawHand = false;

  const model = (name) => (models[name] ||= {
    name, state: "idle", delegate: "", runs: 0, found: 0, errors: 0, consecutiveErrors: 0, lastError: "",
    runningSince: null, lastFoundAt: 0, triedCpu: false, reason: "",
  });

  function register(name, delegate) {
    const m = model(name);
    m.state = "ready"; m.delegate = delegate; m.runningSince = null; m.consecutiveErrors = 0; m.reason = "";
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
    if (m.runningSince === null) m.runningSince = now;
    if (found) {
      m.found++; m.lastFoundAt = now;
      if (name === "face") sawFace = true;
      if (name === "hands") sawHand = true;
    }
    return m;
  }

  // 'cpu' when this GPU model should be rebuilt on the CPU delegate, otherwise ''.
  function fallbackWanted(name) {
    const m = model(name);
    if (m.state !== "ready" || m.delegate !== "GPU" || m.triedCpu) return "";
    if (m.consecutiveErrors >= ERRORS_BEFORE_CPU) return "cpu";
    const blindFor = m.runningSince !== null ? clock() - Math.max(m.runningSince, m.lastFoundAt) : 0;
    if (!sawFace && !sawHand && m.found === 0 && blindFor >= BLIND_MS_BEFORE_CPU) return "cpu";
    return "";
  }
  function markFallback(name, delegate = "CPU") {
    const m = model(name);
    m.triedCpu = true; m.delegate = delegate; m.runningSince = null; m.consecutiveErrors = 0; m.lastFoundAt = 0;
    return m;
  }

  // Presence ("you left the camera") may only be judged once the detector has proven it can see this person.
  function presenceAllowed() {
    return sawFace && model("face").state === "ready";
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
      if (m.consecutiveErrors >= ERRORS_BEFORE_CPU && (m.delegate !== "GPU" || m.triedCpu)) return "detector-errors";
    }
    const ready = [face, hands].filter((m) => m.state === "ready" && m.runningSince !== null);
    if (ready.length && ready.every((m) => (m.delegate === "CPU" || m.triedCpu) && clock() - m.runningSince >= BLIND_MS_BEFORE_TOUCH)) {
      return "no-detections";
    }
    return "";
  }
  // The caller wants to know whether we are still waiting for models (to show a tiny 'getting ready').
  function loading() {
    const face = model("face");
    const hands = model("hands");
    return face.state === "idle" || hands.state === "idle";
  }
  function summary() {
    const out = {sawFace, sawHand};
    for (const [name, m] of Object.entries(models)) {
      out[name] = {state: m.state, delegate: m.delegate, runs: m.runs, found: m.found, errors: m.errors, lastError: m.lastError, reason: m.reason, triedCpu: m.triedCpu};
    }
    return out;
  }

  return {register, fail, run, fallbackWanted, markFallback, presenceAllowed, touchFallback, loading, summary,
    sawPerson: () => sawFace || sawHand};
}

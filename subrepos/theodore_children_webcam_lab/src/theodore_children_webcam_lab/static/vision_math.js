// Pure gesture geometry, with no DOM or camera dependency, so it can be run and
// asserted directly by the test suite instead of only pattern-matched.
//
// MediaPipe landmarks are normalized to the frame, so a raw distance means
// different things depending on how far the child sits from the camera: a hand
// two metres back spans ~0.08 of the frame, one at arm's length ~0.25. Every
// threshold here is therefore in PALMS — multiples of the child's own
// wrist-to-middle-knuckle span — so a fist stays a fist at any distance.

export const FIST_MAX_PALMS = 1.6;     // closed ~1.1, extended ~2.4
export const HEART_TIPS_PALMS = 1.4;   // index fingertips meeting in the cleft
export const HEART_THUMBS_PALMS = 1.6; // thumb tips meeting at the bottom point
export const HEART_WRISTS_PALMS = 1.3; // wrists apart, else it is one clump
export const HEART_CLEFT_PALMS = 0.25; // tips sit below the knuckle peaks
export const HEART_POINT_PALMS = 0.45; // thumbs sit below that cleft
export const HEART_LOBES_PALMS = 1.1;  // knuckles spread into two lobes
export const KISS_NEAR_FACES = 0.85;   // hand-to-mouth, in face widths
export const KISS_AWAY_FACES = 1.5;    // travel needed to count as sent

// MediaPipe hand topology. Used when the runtime does not publish HAND_CONNECTIONS.
export const HAND_BONES = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
];

// object-fit: cover. Landmarks are fractions of the camera frame, and the
// stage crops that frame, so mapping them onto the full stage draws the
// skeleton off the hand. No video yet (pointer demo) uses the whole stage.
export function coverFrame(stageW, stageH, videoW, videoH) {
  const w = Number(stageW) || 0;
  const h = Number(stageH) || 0;
  const vw = Number(videoW) || 0;
  const vh = Number(videoH) || 0;
  if (!w || !h || !vw || !vh) return { x: 0, y: 0, w: w || 1, h: h || 1 };
  const scale = Math.max(w / vw, h / vh);
  const dw = vw * scale;
  const dh = vh * scale;
  return { x: (w - dw) / 2, y: (h - dh) / 2, w: dw, h: dh };
}

// The camera element is mirrored. Flip x inside the covered frame.
export function mapMirroredLandmark(point, frame) {
  const x = Number(point?.x) || 0;
  const y = Number(point?.y) || 0;
  return {
    x: frame.x + (1 - x) * frame.w,
    y: frame.y + y * frame.h,
    z: Number(point?.z) || 0,
  };
}

export function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

// Wrist to middle-finger knuckle: the one span that does not change when the
// fingers curl, so it is a stable ruler for every other measurement.
export function palmSpan(points) {
  const wrist = points?.[0];
  const knuckle = points?.[9];
  return wrist && knuckle ? Math.max(1e-4, distance(wrist, knuckle)) : 1;
}

// Comparing y alone only worked for an upright hand; a tilted or sideways hand
// read as "curled". Farther from the wrist than the middle joint is rotation-proof.
export function fingerExtended(points, tip, pip, margin = 0.22) {
  const wrist = points?.[0];
  if (!wrist || !points?.[tip] || !points?.[pip]) return false;
  const slack = Number.isFinite(margin) ? margin : 0.22;
  return (
    distance(points[tip], wrist) >
    distance(points[pip], wrist) + slack * palmSpan(points)
  );
}

export function handShape(points) {
  if (!points?.length) return null;
  const scale = palmSpan(points);
  const fingers = [
    fingerExtended(points, 8, 6),
    fingerExtended(points, 12, 10),
    fingerExtended(points, 16, 14),
    fingerExtended(points, 20, 18),
  ];
  const thumbOut = fingerExtended(points, 4, 2);
  const count = fingers.filter(Boolean).length + (thumbOut ? 1 : 0);
  const wrist = points[0];
  // A fist is the four fingertips gathered near the wrist, in palms. One
  // noisy "extended" flag does not open the hand if every tip is still close.
  let farthest = 99;
  if (wrist) {
    farthest = 0;
    for (const id of [8, 12, 16, 20]) {
      if (!points[id]) { farthest = 99; break; }
      farthest = Math.max(farthest, distance(points[id], wrist) / scale);
    }
  }
  const tipPalms = wrist && points[8] ? distance(points[8], wrist) / scale : 99;
  return {
    scale,
    count,
    thumbOut,
    tipPalms,
    fingers,
    indexUp: fingers[0] && !fingers[1] && !fingers[2] && !fingers[3],
    fist: farthest < FIST_MAX_PALMS,
  };
}

// Coloring and tracing lift when the whole hand is a fist. Target hits do not
// use this: one raised finger still counts via activeFingertips.
export function fingersPointed(shape) {
  return Boolean(shape) && !shape.fist && Number(shape.count) > 0;
}

// Thumb, index, middle, ring, pinky. Wrist 0 and the palm knuckles are not
// touch points, so a closed palm does not activate a target by itself.
export const FINGERTIP_LANDMARKS = [4, 8, 12, 16, 20];
const FINGERTIP_JOINTS = [[4, 2], [8, 6], [12, 10], [16, 14], [20, 18]];
// A curled tip sits about one palm from the wrist. Closer than this is the palm.
export const PALM_BURY_PALMS = 1.08;
export const TOUCH_MIN_PALMS = 1.55;
export const TOUCH_MIN_PALMS_YOUNG = 1.22;
const YOUNG_TOUCH_MARGIN = 0.06;
const OLDER_TOUCH_MARGIN = 0.22;

export function normalizeTouchAge(value) {
  const raw = String(value ?? "").trim().toLowerCase().replace("–", "-");
  if (!raw) return "";
  if (raw === "4-6" || raw === "child" || raw === "kids" || raw === "young") return "4-6";
  if (raw === "7-10" || raw === "older") return "7-10";
  if (raw === "11-17" || raw === "teen" || raw === "teens") return "11-17";
  if (raw === "adult" || raw === "adults" || raw === "18+") return "adult";
  const age = Number(raw);
  if (Number.isFinite(age) && age >= 1 && age <= 120) {
    if (age < 7) return "4-6";
    if (age < 11) return "7-10";
    return age < 18 ? "11-17" : "adult";
  }
  return "";
}

// A launch query, then a numeric age, then the coarse account band. The number
// wins over child/teen/adult because it can tell 5 from 9.
export function profileTouchAge({ query = "", ageYears = "", ageBand = "" } = {}) {
  return normalizeTouchAge(query) || normalizeTouchAge(ageYears) || normalizeTouchAge(ageBand) || "";
}

export function isYoungTouchAge(ageBand) {
  return normalizeTouchAge(ageBand) === "4-6";
}

// Any fingertip that is actually out, including a point on an otherwise closed
// hand. Tips buried in the palm never count. Younger bands accept a shorter reach.
export function activeFingertips(points, ageBand) {
  if (!points?.length || !points[0]) return [];
  const young = isYoungTouchAge(ageBand);
  const margin = young ? YOUNG_TOUCH_MARGIN : OLDER_TOUCH_MARGIN;
  const minPalms = young ? TOUCH_MIN_PALMS_YOUNG : TOUCH_MIN_PALMS;
  const scale = palmSpan(points);
  const wrist = points[0];
  const tips = [];
  for (const [tip, pip] of FINGERTIP_JOINTS) {
    const point = points[tip];
    if (!point) continue;
    const palms = distance(point, wrist) / scale;
    if (palms < PALM_BURY_PALMS) continue;
    const extended = fingerExtended(points, tip, pip, margin);
    if (extended || palms >= minPalms) tips.push(tip);
  }
  return tips;
}

export function tipHitsTarget(tips, target, radius) {
  if (!target || !Number.isFinite(target.x) || !Number.isFinite(target.y)) return false;
  const reach = Number(radius);
  if (!Number.isFinite(reach) || reach <= 0) return false;
  return (Array.isArray(tips) ? tips : []).some((tip) => (
    tip && Number.isFinite(tip.x) && Number.isFinite(tip.y)
    && Math.hypot(tip.x - target.x, tip.y - target.y) <= reach
  ));
}

export function catchRadiusPx(minSide, ageBand) {
  const side = Math.max(0, Number(minSide) || 0);
  const young = isYoungTouchAge(ageBand);
  return Math.max(young ? 88 : 64, side * (young ? 0.14 : 0.09));
}

// One activation per target until the wait expires, so several fingertips
// or a held pose do not fire the same pop again.
export function claimTouch(latch, key, now, waitMs = 420) {
  const current = latch && typeof latch === "object" ? latch : { key: "", until: 0 };
  const at = Number(now) || 0;
  if (current.key === key && at < Number(current.until || 0)) {
    return { claimed: false, latch: current };
  }
  const wait = Number.isFinite(waitMs) ? waitMs : 420;
  return { claimed: true, latch: { key: String(key), until: at + wait } };
}

/** The slingshot aim: from the pulled-back fist toward where the grab started. */
export function pullAim(tracker) {
  if (!tracker?.grabPoint || !tracker?.cockPoint) return null;
  const x = tracker.grabPoint.x - tracker.cockPoint.x;
  const y = tracker.grabPoint.y - tracker.cockPoint.y;
  const length = Math.hypot(x, y);
  if (length < 1e-6) return null;
  return {origin: tracker.smooth ? {x: tracker.smooth.x, y: tracker.smooth.y} : tracker.cockPoint, dir: {x: x / length, y: y / length}};
}

export function newThrowTracker(side = null) {
  return {
    side,
    phase: "ready",
    grabStartedAt: 0,
    grabPoint: null,
    cockPoint: null,
    history: [],
    smooth: null,
    lastSeenAt: 0,
  };
}

function throwSample(sample) {
  if (!sample?.point || !Number.isFinite(sample.point.x) || !Number.isFinite(sample.point.y)) return null;
  const at = Number(sample.at);
  const palm = Number(sample.palm);
  if (!Number.isFinite(at) || !Number.isFinite(palm) || palm <= 0) return null;
  return {
    at,
    palm,
    fist: Boolean(sample.fist),
    point: {x: Number(sample.point.x), y: Number(sample.point.y)},
  };
}

export function advanceThrowGesture(current, rawSample, ageBand = "7-10") {
  const prior = current?.phase ? current : newThrowTracker();
  const sample = throwSample(rawSample);
  if (!sample) {
    const missingAt = Number(rawSample?.at) || prior.lastSeenAt;
    if (missingAt - prior.lastSeenAt > 320) {
      return {tracker: newThrowTracker(prior.side), event: "lost"};
    }
    return {tracker: prior, event: null};
  }

  // Forgiving on purpose: a webcam sees a hand at 15-30 frames a second, so a
  // quick throw may be only two or three samples. The history is long enough for
  // a slow camera and the pull-back thresholds are small.
  const young = isYoungTouchAge(ageBand);
  const holdMs = young ? 80 : 110;
  const pullPalms = young ? 0.38 : 0.5;
  const speedPalmsPerSecond = young ? 1.2 : 1.6;
  const history = [...(prior.history || []), sample]
    .filter((row) => sample.at - row.at <= 420)
    .slice(-14);
  // Webcam landmarks jitter a few pixels a frame. Smooth the point: heavy when the
  // hand is nearly still (kills jitter), light when it moves fast (no lag).
  const prev = prior.smooth;
  let point = sample.point;
  if (prev && sample.at - prev.at < 300) {
    const speed = Math.hypot(sample.point.x - prev.x, sample.point.y - prev.y) / sample.palm;
    const alpha = Math.max(0.35, Math.min(1, 0.35 + speed * 1.2));
    point = {x: prev.x + (sample.point.x - prev.x) * alpha, y: prev.y + (sample.point.y - prev.y) * alpha};
  }
  sample.point = point;
  const tracker = {...prior, history, smooth: {x: point.x, y: point.y, at: sample.at}, lastSeenAt: sample.at};

  if (tracker.phase === "ready") {
    if (!sample.fist) return {tracker: {...tracker, grabStartedAt: 0, grabPoint: null}, event: null};
    const started = tracker.grabStartedAt || sample.at;
    const grabPoint = tracker.grabPoint || sample.point;
    if (sample.at - started >= holdMs) {
      return {
        tracker: {...tracker, phase: "grabbed", grabStartedAt: started, grabPoint},
        event: "grabbed",
      };
    }
    return {tracker: {...tracker, grabStartedAt: started, grabPoint}, event: null};
  }

  if (tracker.phase === "grabbed") {
    if (!sample.fist) return {tracker: newThrowTracker(prior.side), event: "released-early"};
    const pull = Math.hypot(
      sample.point.x - tracker.grabPoint.x,
      sample.point.y - tracker.grabPoint.y,
    ) / sample.palm;
    if (pull >= pullPalms) {
      return {
        tracker: {...tracker, phase: "cocked", cockPoint: sample.point},
        event: "cocked",
      };
    }
    return {tracker, event: null};
  }

  if (tracker.phase === "cocked") {
    if (sample.fist) {
      const fromGrab = Math.hypot(
        sample.point.x - tracker.grabPoint.x,
        sample.point.y - tracker.grabPoint.y,
      );
      const previous = tracker.cockPoint
        ? Math.hypot(
          tracker.cockPoint.x - tracker.grabPoint.x,
          tracker.cockPoint.y - tracker.grabPoint.y,
        )
        : 0;
      return {
        tracker: fromGrab > previous ? {...tracker, cockPoint: sample.point} : tracker,
        event: null,
      };
    }
    const baseline = history.find((row) => row.at >= sample.at - 360 && row.at < sample.at) || history[0];
    const elapsed = Math.max(16, sample.at - (baseline?.at ?? sample.at - 16));
    const velocity = {
      x: (sample.point.x - (baseline?.point.x ?? sample.point.x)) * 1000 / elapsed,
      y: (sample.point.y - (baseline?.point.y ?? sample.point.y)) * 1000 / elapsed,
    };
    const speed = Math.hypot(velocity.x, velocity.y) / sample.palm;
    const pull = {
      x: tracker.cockPoint.x - tracker.grabPoint.x,
      y: tracker.cockPoint.y - tracker.grabPoint.y,
    };
    const pullLength = Math.hypot(pull.x, pull.y);
    const velocityLength = Math.max(1e-6, Math.hypot(velocity.x, velocity.y));
    const reversal = (pull.x * velocity.x + pull.y * velocity.y) / (Math.max(1e-6, pullLength) * velocityLength);
    const fast = speed >= speedPalmsPerSecond && reversal < 0.2;
    const aim = pullAim(tracker);
    if (aim) {
      // Aim along the slingshot line (the pull-back is long and steady; a release
      // flick is two or three noisy frames). A clear flick only nudges it.
      let dir = aim.dir;
      if (fast) {
        const vx = velocity.x / velocityLength;
        const vy = velocity.y / velocityLength;
        const mixed = {x: dir.x * 0.75 + vx * 0.25, y: dir.y * 0.75 + vy * 0.25};
        const length = Math.hypot(mixed.x, mixed.y);
        if (length > 0.3) dir = {x: mixed.x / length, y: mixed.y / length};
      }
      const nominal = Math.max(speed, speedPalmsPerSecond) * sample.palm;
      return {
        tracker: {...tracker, phase: "released"},
        event: "released",
        release: {origin: sample.point, velocity: {x: dir.x * nominal, y: dir.y * nominal}, speed: Math.max(speed, speedPalmsPerSecond), reversal, assisted: !fast, history, side: tracker.side || null},
      };
    }
    return {tracker: newThrowTracker(prior.side), event: "weak-release"};
  }

  return {tracker: newThrowTracker(prior.side), event: null};
}

export function projectThrowTarget(origin, velocity, targets, fallbackRadius = 64) {
  if (!origin || !velocity) return null;
  const magnitude = Math.hypot(Number(velocity.x) || 0, Number(velocity.y) || 0);
  if (magnitude <= 0) return null;
  const unit = {x: velocity.x / magnitude, y: velocity.y / magnitude};
  const hits = [];
  for (const target of Array.isArray(targets) ? targets : []) {
    if (!Number.isFinite(target?.x) || !Number.isFinite(target?.y)) continue;
    const dx = target.x - origin.x;
    const dy = target.y - origin.y;
    const travel = dx * unit.x + dy * unit.y;
    if (travel <= 0) continue;
    const perpendicular = Math.abs(dx * unit.y - dy * unit.x);
    const radius = Math.max(1, Number(target.radius) || Number(fallbackRadius) || 1);
    if (perpendicular <= radius) hits.push({...target, travel, perpendicular});
  }
  hits.sort((a, b) => a.perpendicular - b.perpendicular || a.travel - b.travel);
  return hits[0] || null;
}

export function heartRatios(a, b, scale) {
  if (!a?.[8] || !b?.[8] || !a[4] || !b[4] || !a[0] || !b[0] || !a[5] || !b[5]) return null;
  const tipY = (a[8].y + b[8].y) / 2;
  const knuckleY = (a[5].y + b[5].y) / 2;
  const thumbY = (a[4].y + b[4].y) / 2;
  return {
    tips: distance(a[8], b[8]) / scale,
    thumbs: distance(a[4], b[4]) / scale,
    wrists: distance(a[0], b[0]) / scale,
    // A heart dips between two lobes. A circle peaks at the fingertips, so this
    // is negative and the pose is rejected.
    cleft: (tipY - knuckleY) / scale,
    point: (thumbY - tipY) / scale,
    lobes: distance(a[5], b[5]) / scale,
  };
}

export function isHeartShape(ratios) {
  return (
    Boolean(ratios) &&
    ratios.tips < HEART_TIPS_PALMS &&
    ratios.thumbs < HEART_THUMBS_PALMS &&
    ratios.wrists > HEART_WRISTS_PALMS &&
    ratios.cleft > HEART_CLEFT_PALMS &&
    ratios.point > HEART_POINT_PALMS &&
    ratios.lobes > HEART_LOBES_PALMS &&
    ratios.lobes > ratios.tips + 0.4
  );
}

// Pointer-demo stand-in for MediaPipe: 21 landmarks in normalised frame space
// so the same handShape / heart / fist code runs without a camera.
export function syntheticHand(tip, { pose = "open", scale = 0.1 } = {}) {
  const nx = Math.max(0.08, Math.min(0.92, tip.x));
  const ny = Math.max(0.08, Math.min(0.75, tip.y));
  const wrist = { x: nx, y: ny + scale, z: 0 };
  const knuckle = { x: nx, y: ny + scale * 0.45, z: 0 };
  const pts = Array.from({ length: 21 }, () => ({ x: nx, y: ny, z: 0 }));
  pts[0] = wrist;
  pts[9] = knuckle;
  pts[2] = { x: nx - scale * 0.15, y: knuckle.y, z: 0 };
  const curledY = knuckle.y + scale * 0.08;
  const openY = ny - scale * 0.05;
  const fingerTips = [
    [8, 6, 0],
    [12, 10, 0.18],
    [16, 14, 0.32],
    [20, 18, 0.46],
  ];
  for (const [tipIdx, pipIdx, dx] of fingerTips) {
    const extend = pose === "open" || (pose === "index" && tipIdx === 8);
    // The index pose's fingertip is the pointer itself, so a trail drawn from
    // landmark 8 sits on the finger instead of above the palm.
    if (pose === "index" && tipIdx === 8) {
      pts[8] = { x: nx, y: ny, z: 0 };
      pts[6] = { x: nx, y: ny + scale * 0.34, z: 0 };
      continue;
    }
    // A fist is a visible knuckle row with the tips curled back toward the
    // wrist, not four landmarks stacked on one pixel.
    if (pose === "fist") {
      const spread = (dx - 0.16) * scale;
      pts[tipIdx] = { x: nx + spread, y: ny + scale * 0.62, z: 0 };
      pts[pipIdx] = { x: nx + spread, y: ny + scale * 0.48, z: 0 };
      continue;
    }
    pts[tipIdx] = { x: nx + dx * scale, y: extend ? openY : curledY, z: 0 };
    pts[pipIdx] = { x: nx + dx * scale * 0.5, y: knuckle.y, z: 0 };
  }
  pts[4] = {
    x: nx - scale * (pose === "fist" ? 0.08 : 0.45),
    y: pose === "fist" ? curledY : openY + scale * 0.12,
    z: 0,
  };
  return pts;
}

// A letter trace is a stroke, not a filled shape. A short line down the guide
// is enough. A tap or a scribble that never crosses the letter is not.
export function traceProgress(points, ageBand) {
  const samples = Array.isArray(points) ? points : [];
  const inside = samples.filter((point) => (
    point.x >= 0.22 && point.x <= 0.78 && point.y >= 0.18 && point.y <= 0.82
  ));
  let length = 0;
  for (let i = 1; i < inside.length; i += 1) {
    length += Math.hypot(inside[i].x - inside[i - 1].x, inside[i].y - inside[i - 1].y);
  }
  let minX = 1;
  let maxX = 0;
  let minY = 1;
  let maxY = 0;
  for (const point of inside) {
    minX = Math.min(minX, point.x);
    maxX = Math.max(maxX, point.x);
    minY = Math.min(minY, point.y);
    maxY = Math.max(maxY, point.y);
  }
  const span = inside.length ? Math.hypot(maxX - minX, maxY - minY) : 0;
  const young = ageBand === "4-6";
  const needLength = young ? 0.32 : 0.42;
  const needSpan = young ? 0.18 : 0.24;
  const needPoints = young ? 6 : 8;
  const insideRatio = samples.length ? inside.length / samples.length : 0;
  const percent = Math.round(100 * Math.min(
    1,
    length / needLength,
    span / needSpan,
    inside.length / needPoints,
    insideRatio / 0.25,
  ));
  return {
    percent: Number.isFinite(percent) ? percent : 0,
    passed: length >= needLength && span >= needSpan && inside.length >= needPoints && insideRatio >= 0.25,
    cells: inside.length,
  };
}

// Attention / away windows. Numbers stay aligned with
// aoep_shared.learner_focus and apps/web/app/lib/learnerFocus.ts.
// Pitch uses the face-mesh hairline-to-chin ratio (positive = down), the same
// proxy as theodore_webcam_lab stare_geometry. Eye gaze is the debiased
// eyeLook blendshape difference. YuNet's five points do not set allowPoseOnly.
export const AWAY_HOLD_MS = 800;
export const RETURN_HOLD_MS = 1200;
export const SIGNAL_HOLD_MS = 1500;
export const BLIND_ARM_MS = 8000;
export const PHONE_PITCH_WITH_GAZE_DEG = 18;
export const PHONE_PITCH_POSE_ONLY_DEG = 28;
export const GAZE_DOWN_MIN = 0.38;
export const YAW_AWAY_DEG = 25;
export const PAUSE_LINE = "We detected that you left the camera. The lesson is paused and will resume when you return.";
export const RESUME_LINE = "You're back on the camera. We'll continue from the same place.";
export const PHONE_LINE = "Looks like you might be looking down at a phone. The lesson is still here when you look up.";
export const LOOK_AWAY_LINE = "Look back at the screen when you can. I'll keep going from here.";
export const LEFT_LINE = "We detected that you left the camera. The lesson is paused and will resume when you return.";

function labLine(fallback, key) {
  try {
    const pack = window.__LAB_CHROME;
    if (pack && pack[key]) return pack[key];
  } catch (e) { /* tests and non-browser imports keep the English line */ }
  return fallback;
}

const NEUTRAL_FACE_UPPER_FRACTION = 0.42;
const FACE_FRACTION_DEG_PER_UNIT = 250;
const GEOMETRIC_PITCH_LIMIT_DEG = 60;

export function geometricPitchDeg(upper, lower) {
  const total = Number(upper) + Number(lower);
  if (!Number.isFinite(total) || total <= 1e-6) return null;
  const fraction = upper / total;
  const deg = (fraction - NEUTRAL_FACE_UPPER_FRACTION) * FACE_FRACTION_DEG_PER_UNIT;
  return Math.max(-GEOMETRIC_PITCH_LIMIT_DEG, Math.min(GEOMETRIC_PITCH_LIMIT_DEG, deg));
}

// Spans sit on the face's own vertical axis so roll cancels. Landmark x is
// scaled by frame aspect because x and y are normalized separately.
export function headPoseFromMesh(points, aspect = 1) {
  if (!points) return null;
  const left = points[33];
  const right = points[263];
  const chin = points[152];
  const forehead = points[10];
  const nose = points[1];
  if (!left || !right || !chin || !forehead || !nose) return null;
  const ar = Number.isFinite(aspect) && aspect > 0 ? aspect : 1;
  const ex = (right.x - left.x) * ar;
  const ey = right.y - left.y;
  const elen = Math.hypot(ex, ey);
  if (elen <= 1e-6) return null;
  let vx = -ey / elen;
  let vy = ex / elen;
  const midX = ((left.x + right.x) / 2) * ar;
  const midY = (left.y + right.y) / 2;
  const along = (point) => (point.x * ar - midX) * vx + (point.y - midY) * vy;
  if (along(chin) < 0) {
    vx = -vx;
    vy = -vy;
  }
  const pitch = geometricPitchDeg(-along(forehead), along(chin));
  if (pitch == null) return null;
  const yaw = Math.max(-60, Math.min(60, (nose.x - (left.x + right.x) / 2) * 120));
  const iod = Math.hypot((right.x - left.x) * ar, right.y - left.y) || 1;
  const frontal = Math.max(0, Math.min(1, 1 - (Math.abs(nose.x - (left.x + right.x) / 2) / iod) * 1.6));
  return { pitch, yaw, frontal };
}

export function debiasedGazeDown(blendshapes) {
  const bs = blendshapes || {};
  const lookDown = ((bs.eyeLookDownLeft || 0) + (bs.eyeLookDownRight || 0)) / 2;
  const lookUp = ((bs.eyeLookUpLeft || 0) + (bs.eyeLookUpRight || 0)) / 2;
  return Math.max(0, Math.min(1, (lookDown - lookUp - 0.25) / 0.5));
}

function phoneSignal(sample) {
  const pitch = sample.pitchDeg;
  if (pitch == null || !Number.isFinite(pitch)) return null;
  if (sample.gazeDown != null && Number.isFinite(sample.gazeDown)) {
    return pitch >= PHONE_PITCH_WITH_GAZE_DEG && sample.gazeDown >= GAZE_DOWN_MIN
      ? "pitch_and_gaze"
      : null;
  }
  if (sample.allowPoseOnly && pitch >= PHONE_PITCH_POSE_ONLY_DEG) return "head_pose_only";
  return null;
}

export function createPresenceWatch() {
  const watch = {
    phase: "unknown",
    awaySince: null,
    backSince: null,
    awayStarted: 0,
    phoneSince: null,
    lookSince: null,
    phoneOpen: false,
    lookOpen: false,
    seenFace: false,
    started: null,
  };
  return {
    update(sample) {
      const now = Number(sample.atMs) || 0;
      if (watch.started == null) watch.started = now;
      const face = Boolean(sample.facePresent);
      const events = [];
      if (face) {
        watch.seenFace = true;
        watch.awaySince = null;
        if (watch.phase === "away") {
          if (watch.backSince == null) watch.backSince = now;
          if (now - watch.backSince >= RETURN_HOLD_MS) {
            const awayMs = Math.max(0, now - watch.awayStarted);
            watch.phase = "here";
            watch.backSince = null;
            events.push({
              type: "resume",
              kind: "returned",
              line: labLine(RESUME_LINE, "resumeLine"),
              awayMs,
              atMs: now,
              signal: sample.source || "",
            });
          }
        } else if (watch.phase === "unknown") {
          watch.phase = "here";
        }
        if (watch.phase === "here") events.push(...attentionEvents(watch, sample, now));
        return events;
      }
      watch.backSince = null;
      watch.phoneSince = null;
      watch.lookSince = null;
      watch.phoneOpen = false;
      watch.lookOpen = false;
      if (sample.explicitAway) {
        if (watch.phase !== "away") {
          watch.phase = "away";
          watch.awayStarted = now;
          watch.awaySince = now;
          events.push({
            type: "pause",
            kind: "left_frame",
            line: labLine(PAUSE_LINE, "pauseLine"),
            atMs: now,
            signal: sample.source || "explicit",
          });
        }
        return events;
      }
      const armed = watch.seenFace || now - watch.started >= BLIND_ARM_MS;
      if (!armed) return events;
      if (watch.awaySince == null) watch.awaySince = now;
      const held = watch.seenFace ? AWAY_HOLD_MS : 0;
      if (watch.phase !== "away" && now - watch.awaySince >= held) {
        watch.phase = "away";
        watch.awayStarted = watch.awaySince;
        events.push({
          type: "pause",
          kind: "left_frame",
          line: labLine(PAUSE_LINE, "pauseLine"),
          notice: labLine(LEFT_LINE, "pauseLine"),
          atMs: now,
          signal: sample.source || "no_face",
        });
      }
      return events;
    },
  };
}

function attentionEvents(watch, sample, now) {
  const events = [];
  const phone = phoneSignal(sample);
  if (phone) {
    if (watch.phoneSince == null) watch.phoneSince = now;
    if (!watch.phoneOpen && now - watch.phoneSince >= SIGNAL_HOLD_MS) {
      watch.phoneOpen = true;
      events.push({
        type: "notice",
        kind: "looking_at_phone",
        line: PHONE_LINE,
        signal: phone,
        atMs: now,
      });
    }
  } else {
    watch.phoneSince = null;
    watch.phoneOpen = false;
  }
  const yaw = sample.yawDeg;
  const frontal = sample.gazeFrontal;
  const away = phone
    ? null
    : (yaw != null && Math.abs(yaw) >= YAW_AWAY_DEG
      ? "yaw"
      : (frontal != null && frontal < 0.4 ? "gaze_frontal" : null));
  if (away) {
    if (watch.lookSince == null) watch.lookSince = now;
    if (!watch.lookOpen && now - watch.lookSince >= SIGNAL_HOLD_MS) {
      watch.lookOpen = true;
      events.push({
        type: "notice",
        kind: "looking_away",
        line: LOOK_AWAY_LINE,
        signal: away,
        atMs: now,
      });
    }
  } else {
    watch.lookSince = null;
    watch.lookOpen = false;
  }
  return events;
}

// Mirror Hall. A beat is three lights — head and both hands — in stage
// fractions (y grows downward). Matching uses position only. Expressions are
// not part of the score.
export const MIRROR_HOLD_MS = 400;
export const MIRROR_SEATED_MAX_Y = 0.58;
export const MIRROR_PACES = {
  easy: { id: "easy", radius: 0.18, windowMs: 2200, retries: 1 },
  family: { id: "family", radius: 0.12, windowMs: 1500, retries: 0 },
  sharp: { id: "sharp", radius: 0.075, windowMs: 900, retries: 0 },
};
export const MIRROR_ROUTINE = [
  { id: "hands-up", prompt: "Hands up", head: { x: 0.5, y: 0.34 }, left: { x: 0.34, y: 0.12 }, right: { x: 0.66, y: 0.12 } },
  { id: "wide-star", prompt: "Make a star", head: { x: 0.5, y: 0.3 }, left: { x: 0.14, y: 0.62 }, right: { x: 0.86, y: 0.62 } },
  { id: "hands-together", prompt: "Hands together", head: { x: 0.5, y: 0.38 }, left: { x: 0.46, y: 0.16 }, right: { x: 0.54, y: 0.16 } },
  { id: "one-hand-high", prompt: "One hand high", head: { x: 0.5, y: 0.32 }, left: { x: 0.3, y: 0.1 }, right: { x: 0.68, y: 0.4 } },
  { id: "lean-left", prompt: "Lean left", head: { x: 0.34, y: 0.36 }, left: { x: 0.16, y: 0.22 }, right: { x: 0.48, y: 0.28 } },
  { id: "lean-right", prompt: "Lean right", head: { x: 0.66, y: 0.36 }, left: { x: 0.52, y: 0.28 }, right: { x: 0.84, y: 0.22 } },
  { id: "frame-face", prompt: "Frame your face", head: { x: 0.5, y: 0.36 }, left: { x: 0.34, y: 0.32 }, right: { x: 0.66, y: 0.32 } },
  { id: "freeze", prompt: "Freeze", head: { x: 0.5, y: 0.3 }, left: { x: 0.36, y: 0.78 }, right: { x: 0.64, y: 0.78 } },
];

export function mirrorPace(pace) {
  const key = String(pace || "").trim().toLowerCase();
  return MIRROR_PACES[key] || MIRROR_PACES.family;
}

export function defaultMirrorPace(ageBand) {
  return isYoungTouchAge(ageBand) ? "easy" : "family";
}

export function clampMirrorPoint(point, seated) {
  if (!point) return null;
  const x = Number(point.x);
  const y = Number(point.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y: seated ? Math.min(y, MIRROR_SEATED_MAX_Y) : y };
}

export function mirrorPose(index, { seated = false } = {}) {
  const slot = ((Number(index) || 0) % MIRROR_ROUTINE.length + MIRROR_ROUTINE.length) % MIRROR_ROUTINE.length;
  const beat = MIRROR_ROUTINE[slot];
  return {
    id: beat.id,
    prompt: beat.prompt,
    index: slot,
    head: clampMirrorPoint(beat.head, seated),
    left: clampMirrorPoint(beat.left, seated),
    right: clampMirrorPoint(beat.right, seated),
  };
}

export function mirrorPointHit(live, target, radius) {
  if (!live || !target) return false;
  const reach = Number(radius);
  if (![live.x, live.y, target.x, target.y, reach].every(Number.isFinite) || reach <= 0) return false;
  return Math.hypot(live.x - target.x, live.y - target.y) <= reach;
}

export function mirrorBeatMatched(live, pose, radius) {
  if (!live || !pose) return false;
  return mirrorPointHit(live.head, pose.head, radius)
    && mirrorPointHit(live.left, pose.left, radius)
    && mirrorPointHit(live.right, pose.right, radius);
}

export function mirrorStars(hits, total = MIRROR_ROUTINE.length) {
  const beats = Number(total) > 0 ? Number(total) : MIRROR_ROUTINE.length;
  const ratio = Math.max(0, Number(hits) || 0) / beats;
  if (ratio >= 0.85) return 3;
  if (ratio >= 0.6) return 2;
  return 1;
}

export function mirrorSummary(run) {
  const hits = Math.max(0, Number(run?.hits) || 0);
  const total = MIRROR_ROUTINE.length;
  const bestCombo = Math.max(0, Number(run?.bestCombo) || 0);
  const stars = mirrorStars(hits, total);
  return {
    hits,
    total,
    bestCombo,
    stars,
    line: `${hits} of ${total} lights. Best combo ${bestCombo}.`,
  };
}

export function freshMirrorRun(pace) {
  const chosen = mirrorPace(pace);
  return {
    index: 0,
    hits: 0,
    combo: 0,
    bestCombo: 0,
    retries: 0,
    windowStart: null,
    matchedSince: null,
    finished: false,
    pace: chosen.id,
    lastEvent: "",
  };
}

function mirrorFailBeat(run, pace, now) {
  if (run.retries < pace.retries) {
    return {
      ...run,
      retries: run.retries + 1,
      windowStart: now,
      matchedSince: null,
      event: "retry",
    };
  }
  return mirrorAdvanceBeat({ ...run, combo: 0, matchedSince: null }, "miss");
}

function mirrorAdvanceBeat(run, event) {
  const index = run.index + 1;
  if (index >= MIRROR_ROUTINE.length) {
    return {
      ...run,
      finished: true,
      matchedSince: null,
      event: "done",
      lastEvent: event,
    };
  }
  return {
    ...run,
    index,
    retries: 0,
    windowStart: null,
    matchedSince: null,
    event,
    lastEvent: event,
  };
}

// One frame of a Mirror Hall beat. `matched` means the head and both hands
// are inside the pace radius right now. A hit needs that to stay true for
// MIRROR_HOLD_MS before the window ends. Easy may repeat a missed beat once.
export function advanceMirrorBeat(run, { matched = false, now = 0 } = {}) {
  const pace = mirrorPace(run?.pace);
  const next = {
    index: Math.max(0, Number(run?.index) || 0),
    hits: Math.max(0, Number(run?.hits) || 0),
    combo: Math.max(0, Number(run?.combo) || 0),
    bestCombo: Math.max(0, Number(run?.bestCombo) || 0),
    retries: Math.max(0, Number(run?.retries) || 0),
    windowStart: Number.isFinite(run?.windowStart) ? run.windowStart : now,
    matchedSince: Number.isFinite(run?.matchedSince) ? run.matchedSince : null,
    finished: Boolean(run?.finished),
    pace: pace.id,
    lastEvent: run?.lastEvent || "",
  };
  if (next.finished) return { ...next, event: "done" };
  const expireAt = next.windowStart + pace.windowMs;
  if (matched) {
    if (!Number.isFinite(next.matchedSince)) next.matchedSince = now;
    if (now - next.matchedSince >= MIRROR_HOLD_MS) {
      next.hits += 1;
      next.combo += 1;
      next.bestCombo = Math.max(next.bestCombo, next.combo);
      return mirrorAdvanceBeat(next, "hit");
    }
    if (now >= expireAt) return mirrorFailBeat(next, pace, now);
    return { ...next, event: "hold" };
  }
  next.matchedSince = null;
  if (now >= expireAt) return mirrorFailBeat(next, pace, now);
  return { ...next, event: "waiting" };
}

// Original Ninja Weave vocabulary. Every sign is a plain two-hand pose built
// from five everyday hand shapes and three placements. No names, signs, or
// sequences come from an existing franchise.
export const NINJA_HAND_SHAPES = {
  fist: { id: "fist", word: "Stone", glyph: "✊", how: "a fist" },
  point: { id: "point", word: "Needle", glyph: "☝️", how: "one finger up" },
  open: { id: "open", word: "Leaf", glyph: "🖐️", how: "an open hand" },
  peace: { id: "peace", word: "Twin", glyph: "✌️", how: "two fingers up" },
  horns: { id: "horns", word: "Hook", glyph: "🤘", how: "first and little finger up" },
};

export const NINJA_PLACEMENTS = {
  together: { id: "together", word: "Gate", how: "hands close together" },
  apart: { id: "apart", word: "Wings", how: "hands wide apart" },
  stacked: { id: "stacked", word: "Tower", how: "one hand above the other" },
};

const NINJA_EASY_SHAPES = new Set(["fist", "point", "open"]);

function ninjaSealLevel(a, b, placement) {
  if (a === "horns" || b === "horns") return 3;
  if (placement === "stacked" || !NINJA_EASY_SHAPES.has(a) || !NINJA_EASY_SHAPES.has(b)) return 2;
  return 1;
}

function buildNinjaSeals() {
  const seals = {};
  for (const placement of Object.values(NINJA_PLACEMENTS)) {
    for (const a of Object.values(NINJA_HAND_SHAPES)) {
      for (const b of Object.values(NINJA_HAND_SHAPES)) {
        const id = `${a.id}-${b.id}-${placement.id}`;
        const label = a.id === b.id
          ? `Double ${a.word} ${placement.word}`
          : `${a.word}-${b.word} ${placement.word}`;
        const [first, second] = placement.id === "stacked" ? ["Top", "bottom"] : ["Left", "right"];
        seals[id] = {
          id,
          label,
          a: a.id,
          b: b.id,
          placement: placement.id,
          level: ninjaSealLevel(a.id, b.id, placement.id),
          glyph: `${a.glyph}${b.glyph}`,
          glyphA: a.glyph,
          glyphB: b.glyph,
          how: `${first} hand ${a.how}, ${second} hand ${b.how}, ${placement.how}.`,
        };
      }
    }
  }
  return seals;
}

export const NINJA_SEALS = buildNinjaSeals();

export const NINJA_ELEMENTS = {
  fire: { id: "fire", label: "Fire", glyph: "🔥", colors: ["#fef08a", "#fb923c", "#dc2626"], particle: "orb", sound: "roar" },
  water: { id: "water", label: "Water", glyph: "💧", colors: ["#ecfeff", "#22d3ee", "#2563eb"], particle: "drop", sound: "splash" },
  earth: { id: "earth", label: "Earth", glyph: "🪨", colors: ["#f5d491", "#a16207", "#422006"], particle: "rock", sound: "rumble" },
  wind: { id: "wind", label: "Wind", glyph: "🌀", colors: ["#f0fdfa", "#99f6e4", "#14b8a6"], particle: "streak", sound: "whoosh" },
  thunder: { id: "thunder", label: "Thunder", glyph: "⚡", colors: ["#fffbeb", "#facc15", "#7c3aed"], particle: "bolt", sound: "zap" },
  ice: { id: "ice", label: "Ice", glyph: "❄️", colors: ["#f8fafc", "#bae6fd", "#38bdf8"], particle: "shard", sound: "chime" },
  sun: { id: "sun", label: "Sun", glyph: "☀️", colors: ["#ffffff", "#fde68a", "#f59e0b"], particle: "star", sound: "shine" },
  moon: { id: "moon", label: "Moon", glyph: "🌙", colors: ["#ede9fe", "#a78bfa", "#4c1d95"], particle: "orb", sound: "hum" },
  leaf: { id: "leaf", label: "Leaf", glyph: "🌿", colors: ["#dcfce7", "#4ade80", "#15803d"], particle: "leaf", sound: "rustle" },
  steel: { id: "steel", label: "Steel", glyph: "⚙️", colors: ["#f8fafc", "#94a3b8", "#334155"], particle: "shard", sound: "clang" },
};

// Ordered from shortest to longest weave. The tier sets the sign count.
export const NINJA_FORMS = [
  { id: "burst", label: "Burst" },
  { id: "ring", label: "Ring" },
  { id: "fountain", label: "Fountain", focus: { x: 0.5, y: 0.85 } },
  { id: "rain", label: "Rain", focus: { x: 0.5, y: 0.2 } },
  { id: "wave", label: "Wave", focus: { x: 0.5, y: 0.8 } },
  { id: "bloom", label: "Bloom" },
  { id: "spiral", label: "Spiral" },
  { id: "comet", label: "Comet", focus: { x: 0.82, y: 0.25 } },
  { id: "pillar", label: "Pillar", focus: { x: 0.5, y: 0.85 }, shake: true },
  { id: "fan", label: "Fan", focus: { x: 0.5, y: 0.82 } },
  { id: "orbit", label: "Orbit" },
  { id: "wall", label: "Wall", focus: { x: 0.5, y: 0.75 }, shake: true },
  { id: "vortex", label: "Vortex" },
  { id: "lance", label: "Lance", focus: { x: 0.88, y: 0.55 } },
  { id: "tide", label: "Tide" },
  { id: "cascade", label: "Cascade", focus: { x: 0.5, y: 0.2 } },
  { id: "shield", label: "Shield", focus: { x: 0.5, y: 0.75 } },
  { id: "nova", label: "Nova" },
  { id: "swarm", label: "Swarm" },
  { id: "quake", label: "Quake", focus: { x: 0.5, y: 0.85 }, shake: true },
  { id: "twin", label: "Twin Burst" },
  { id: "crown", label: "Crown", focus: { x: 0.5, y: 0.4 } },
];

export const NINJA_TIER_LENGTHS = [3, 4, 5, 6];

function ninjaFormTier(index) {
  if (index < 6) return 0;
  if (index < 12) return 1;
  if (index < 17) return 2;
  return 3;
}

// Seeded so every device builds the same sequences and the same effect paths.
export function ninjaRandom(seed) {
  let a = 2166136261;
  for (const ch of String(seed)) a = Math.imul(a ^ ch.charCodeAt(0), 16777619);
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function ninjaShuffle(items, rand) {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function buildNinjaTechniques() {
  const seals = Object.values(NINJA_SEALS);
  const pools = [
    seals.filter((seal) => seal.level === 1),
    seals.filter((seal) => seal.level <= 2),
    seals,
  ].map((pool) => pool.map((seal) => seal.id));
  const rand = ninjaRandom("ninja-weave-v2");
  // The longest weaves deal from a shuffled deck so every sign is used.
  let deck = ninjaShuffle(seals.map((seal) => seal.id), rand);
  let deckAt = 0;
  const dealSeal = () => {
    if (deckAt >= deck.length) {
      deck = ninjaShuffle(deck, rand);
      deckAt = 0;
    }
    return deck[deckAt++];
  };
  const used = new Set();
  const techniques = {};
  NINJA_FORMS.forEach((form, formIndex) => {
    const tier = ninjaFormTier(formIndex);
    const length = NINJA_TIER_LENGTHS[tier];
    for (const element of Object.values(NINJA_ELEMENTS)) {
      let sequence = [];
      for (let attempt = 0; attempt < 40; attempt += 1) {
        sequence = [];
        while (sequence.length < length) {
          const pool = pools[Math.min(tier, 2)];
          const id = tier === 3 ? dealSeal() : pool[Math.floor(rand() * pool.length)];
          if (id !== sequence[sequence.length - 1]) sequence.push(id);
        }
        if (!used.has(sequence.join(" "))) break;
      }
      used.add(sequence.join(" "));
      const id = `${element.id}-${form.id}`;
      techniques[id] = {
        id,
        label: `${element.label} ${form.label}`,
        glyph: element.glyph,
        element: element.id,
        form: form.id,
        tier,
        sequence,
      };
    }
  });
  return techniques;
}

// One technique per finisher effect: element x form.
export const NINJA_TECHNIQUES = buildNinjaTechniques();
export const NINJA_EFFECTS = NINJA_TECHNIQUES;
export const NINJA_DEFAULT_TECHNIQUE = "fire-burst";

export function ninjaTechniqueList(element) {
  const wanted = String(element || "").toLowerCase();
  return NINJA_FORMS
    .map((form) => NINJA_TECHNIQUES[`${wanted}-${form.id}`])
    .filter(Boolean);
}

export function ninjaEffectSpec(id) {
  const technique = ninjaTechnique(id);
  const element = NINJA_ELEMENTS[technique.element];
  const formIndex = NINJA_FORMS.findIndex((form) => form.id === technique.form);
  const form = NINJA_FORMS[formIndex];
  return {
    id: technique.id,
    label: technique.label,
    element: element.id,
    form: form.id,
    colors: element.colors,
    particle: element.particle,
    sound: element.sound,
    focus: form.focus || { x: 0.5, y: 0.5 },
    shake: Boolean(form.shake),
    pitch: Math.round((0.8 + (formIndex % 6) * 0.08) * 100) / 100,
  };
}

const TAU = Math.PI * 2;
const ninjaAt = (radius, angle, cx = 0.5, cy = 0.5) => ({
  x: cx + Math.cos(angle) * radius,
  y: cy + Math.sin(angle) * radius,
});

// Each form returns a path in stage fractions (0..1) plus a start delay in ms.
const NINJA_FORM_PATHS = {
  burst: ({ a, j }) => ({ points: [ninjaAt(0.02, a), ninjaAt(0.3 + j * 0.15, a)], delay: j * 120 }),
  ring: ({ a }) => ({ points: [ninjaAt(0.04, a), ninjaAt(0.36, a)], delay: 0 }),
  fountain: ({ t, j }) => ({
    points: [{ x: 0.5, y: 1.02 }, { x: 0.5 + (t - 0.5) * 0.5, y: 0.18 + j * 0.12 }, { x: 0.5 + (t - 0.5), y: 0.72 }],
    delay: j * 600,
  }),
  rain: ({ t, j }) => ({ points: [{ x: t, y: -0.08 }, { x: t + (j - 0.5) * 0.06, y: 1.06 }], delay: j * 900 }),
  wave: ({ t }) => ({
    points: [{ x: t, y: 1.06 }, { x: t, y: 0.55 + 0.12 * Math.sin(t * 4 * Math.PI) }, { x: t + 0.05, y: 1.06 }],
    delay: t * 500,
  }),
  bloom: ({ a, j }) => ({ points: [ninjaAt(0.02, a), ninjaAt(0.18, a), ninjaAt(0.36, a + 0.7)], delay: j * 150 }),
  spiral: ({ a, t }) => ({
    points: [ninjaAt(0.02, a * 2), ninjaAt(0.2, a * 2 + 1.5), ninjaAt(0.4, a * 2 + 3)],
    delay: t * 450,
  }),
  comet: ({ t, j }) => ({
    points: [{ x: -0.08 + j * 0.05, y: 0.82 + (j - 0.5) * 0.08 }, { x: 1.08, y: 0.18 + (j - 0.5) * 0.12 }],
    delay: t * 550,
  }),
  pillar: ({ t, j }) => ({
    points: [{ x: 0.5 + (j - 0.5) * 0.18, y: 1.06 }, { x: 0.5 + (j - 0.5) * 0.1, y: -0.08 }],
    delay: t * 600,
  }),
  fan: ({ t, j }) => {
    const angle = -Math.PI * (0.15 + 0.7 * t);
    return { points: [ninjaAt(0.03, angle, 0.5, 0.85), ninjaAt(0.55, angle, 0.5, 0.85)], delay: j * 150 };
  },
  orbit: ({ a }) => ({
    points: [ninjaAt(0.3, a), ninjaAt(0.3, a + Math.PI / 2), ninjaAt(0.3, a + Math.PI), ninjaAt(0.3, a + 1.5 * Math.PI)],
    delay: 0,
  }),
  wall: ({ t, j }) => ({
    points: [{ x: t, y: 1.06 }, { x: t, y: 0.58 + j * 0.06 }, { x: t, y: 0.62 }],
    delay: Math.abs(t - 0.5) * 700,
  }),
  vortex: ({ a, j }) => ({ points: [ninjaAt(0.48, a), ninjaAt(0.24, a + 1.6), ninjaAt(0.02, a + 3.2)], delay: j * 300 }),
  lance: ({ t, j }) => ({
    points: [{ x: 0.08, y: 0.55 + (j - 0.5) * 0.05 }, { x: 1.08, y: 0.55 + (t - 0.5) * 0.14 }],
    delay: t * 350,
  }),
  tide: ({ t, a, j }) => ({
    points: [{ x: -0.08, y: 0.25 + t * 0.6 }, { x: 0.5, y: 0.2 + t * 0.6 + 0.05 * Math.sin(a * 3) }, { x: 1.08, y: 0.25 + t * 0.6 }],
    delay: j * 300,
  }),
  cascade: ({ t }) => ({
    points: [{ x: t, y: -0.06 }, { x: t + 0.06, y: 0.35 }, { x: t - 0.06, y: 0.7 }, { x: t, y: 1.06 }],
    delay: t * 500,
  }),
  shield: ({ t }) => {
    const angle = -Math.PI * t;
    return { points: [ninjaAt(0.02, angle, 0.5, 0.75), ninjaAt(0.42, angle, 0.5, 0.75)], delay: t * 300 };
  },
  nova: ({ a, i }) => ({ points: [ninjaAt(0.02, a), ninjaAt(0.12, a), ninjaAt(0.55, a + 0.2)], delay: (i % 2) * 350 }),
  swarm: ({ rand }) => ({
    points: Array.from({ length: 4 }, () => ({ x: 0.5 + (rand() - 0.5) * 0.8, y: 0.5 + (rand() - 0.5) * 0.7 })),
    delay: rand() * 300,
  }),
  quake: ({ t, j }) => ({
    points: [{ x: t, y: 1.06 }, { x: t, y: 0.66 + j * 0.1 }, { x: t + (j - 0.5) * 0.1, y: 1.06 }],
    delay: Math.abs(t - 0.5) * 400,
  }),
  twin: ({ a, i }) => {
    const cx = i % 2 ? 0.3 : 0.7;
    return { points: [ninjaAt(0.02, a, cx), ninjaAt(0.24, a, cx)], delay: (i % 2) * 200 };
  },
  crown: ({ t }) => {
    const angle = -Math.PI * t;
    return { points: [{ x: 0.5, y: 1.02 }, ninjaAt(0.26, angle, 0.5, 0.42)], delay: t * 400 };
  },
};

function ninjaTurn(point, angle) {
  const dx = point.x - 0.5;
  const dy = point.y - 0.5;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return { x: 0.5 + dx * cos - dy * sin, y: 0.5 + dx * sin + dy * cos };
}

function ninjaScale(point, factor) {
  return { x: 0.5 + (point.x - 0.5) * factor, y: 0.5 + (point.y - 0.5) * factor };
}

// Each element moves its particles its own way on top of the form's path:
// fire rises, water falls, wind swirls, thunder zigzags, leaves flutter.
const NINJA_ELEMENT_DRIFT = {
  fire: (p, u) => ({ x: p.x, y: p.y - 0.08 * u }),
  water: (p, u) => ({ x: p.x, y: p.y + 0.06 * u }),
  earth: (p, u) => ({ x: p.x, y: p.y + 0.03 * u * u }),
  wind: (p, u) => ninjaTurn(p, 0.5 * u),
  thunder: (p, u, k) => ({ x: p.x + (k % 2 ? 0.03 : -0.03) * u, y: p.y }),
  ice: (p, u) => ninjaScale(p, 1 - 0.1 * u),
  sun: (p, u) => ninjaScale(p, 1 + 0.12 * u),
  moon: (p, u) => ninjaTurn(p, -0.4 * u),
  leaf: (p, u, k, j) => ({ x: p.x + 0.04 * Math.sin(u * TAU + j * TAU), y: p.y }),
  steel: (p, u) => ({ x: 0.5 + (p.x - 0.5) * (1 + 0.05 * u), y: p.y }),
};

// Pure particle plan for one finisher. The page animates these paths; tests
// check that every one of the effects produces finite, on-stage motion.
export function ninjaEffectParticles(id, count = 24) {
  const technique = ninjaTechnique(id);
  const path = NINJA_FORM_PATHS[technique.form] || NINJA_FORM_PATHS.burst;
  const drift = NINJA_ELEMENT_DRIFT[technique.element] || ((p) => p);
  const rand = ninjaRandom(technique.id);
  const n = Math.max(6, Math.min(48, Math.round(Number(count) || 24)));
  const round = (value) => Math.round(Math.max(-0.2, Math.min(1.2, value)) * 1000) / 1000;
  return Array.from({ length: n }, (_, i) => {
    const t = n > 1 ? i / (n - 1) : 0;
    const j = rand();
    const plan = path({ i, n, t, a: (TAU * i) / n, j, rand });
    let points = plan.points;
    if (points.length === 2) {
      const [from, to] = points;
      points = [from, { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 }, to];
    }
    const last = points.length - 1;
    points = points.map((p, k) => drift(p, k / last, k, j));
    return {
      points: points.map((p) => ({ x: round(p.x), y: round(p.y) })),
      delay: Math.round(plan.delay),
      size: Math.round((0.6 + rand() * 0.8) * 100) / 100,
      spin: Math.round((rand() * 2 - 1) * 360),
    };
  });
}

// A sign is accepted from a few matching camera samples, not one uninterrupted
// hold. This absorbs hand-tracker lag and lets a player correct intermediate
// poses without losing evidence already collected for the requested sign.
export const NINJA_HOLD_MS = 120;
export const NINJA_INITIAL_CREDIT_MS = 55;
export const NINJA_SAMPLE_CAP_MS = 85;
export const NINJA_HOLD_GRACE_MS = 1200;
export const NINJA_RELEASE_MS = 100;
// Placement thresholds as stage fractions. Together and Apart overlap on
// purpose: an in-between spacing satisfies whichever one the weave asks for.
export const NINJA_TOGETHER_MAX = 0.42;
export const NINJA_APART_MIN = 0.18;
export const NINJA_STACK_MIN = 0.12;

export function ninjaTechnique(id) {
  return NINJA_TECHNIQUES[String(id || "").toLowerCase()] || NINJA_TECHNIQUES[NINJA_DEFAULT_TECHNIQUE];
}

function ninjaTwoHands(hands) {
  const two = (Array.isArray(hands) ? hands : [])
    .filter((hand) => hand?.wrist && Number.isFinite(hand.wrist.x) && Number.isFinite(hand.wrist.y))
    .slice(0, 2);
  return two.length === 2 ? two : null;
}

// [index, middle, ring, pinky]. Synthetic or screen hands without per-finger
// flags fall back to fist / indexUp / count.
export function ninjaFingers(hand) {
  if (Array.isArray(hand?.fingers) && hand.fingers.length >= 4) {
    return hand.fingers.slice(0, 4).map(Boolean);
  }
  if (!hand || hand.fist) return [false, false, false, false];
  if (hand.indexUp) return [true, false, false, false];
  const count = Number(hand.count) || 0;
  if (count >= 4) return [true, true, true, true];
  if (count === 3) return [true, true, true, false];
  if (count === 2) return [true, true, false, false];
  if (count === 1) return [true, false, false, false];
  return [false, false, false, false];
}

// Loose per-hand check: one stray finger does not break a shape.
export function ninjaShapeFits(hand, shape) {
  if (!hand) return false;
  const [index, middle, ring, pinky] = ninjaFingers(hand);
  const up = [index, middle, ring, pinky].filter(Boolean).length;
  if (shape === "fist") return Boolean(hand.fist) || up === 0 || (up === 1 && !index);
  if (hand.fist) return false;
  if (shape === "point") return index && !middle && !ring;
  if (shape === "peace") return index && middle && !(ring && pinky);
  if (shape === "open") return up >= 3;
  if (shape === "horns") return index && pinky && !(middle && ring);
  return false;
}

export function ninjaShapeOf(hand) {
  if (!hand) return null;
  const [index, middle, ring, pinky] = ninjaFingers(hand);
  const up = [index, middle, ring, pinky].filter(Boolean).length;
  if (hand.fist || up === 0) return "fist";
  if (up >= 3) return "open";
  if (index && pinky && !middle && !ring) return "horns";
  if (index && middle && !ring && !pinky) return "peace";
  if (index && !middle && !ring) return "point";
  if (up === 1) return "fist";
  return null;
}

function ninjaGap(two, stageWidth, stageHeight) {
  const width = Math.max(1, Number(stageWidth) || 1);
  const height = Math.max(1, Number(stageHeight) || width);
  return {
    dx: Math.abs(two[0].wrist.x - two[1].wrist.x) / width,
    dy: Math.abs(two[0].wrist.y - two[1].wrist.y) / height,
  };
}

function ninjaPlacementFits(placement, { dx, dy }) {
  if (placement === "stacked") return dy >= NINJA_STACK_MIN && dy >= dx * 0.8;
  if (placement === "together") return dx <= NINJA_TOGETHER_MAX && dy <= 0.3;
  if (placement === "apart") return dx >= NINJA_APART_MIN && dy < dx * 1.25;
  return false;
}

function ninjaPlacementOf({ dx, dy }) {
  if (dy >= 0.15 && dy > dx) return "stacked";
  return dx <= 0.3 ? "together" : "apart";
}

// Side-by-side signs read left to right; stacked signs read top to bottom.
function ninjaOrdered(two, placement) {
  const key = placement === "stacked" ? "y" : "x";
  return [...two].sort((p, q) => p.wrist[key] - q.wrist[key]);
}

// True when the hands are close enough to the sign the weave is waiting for.
// The readout can still name a different best guess; this is the looser check.
// mirrorOk also accepts the two hand shapes swapped (Easy pace).
export function ninjaSealFits(hands, expected, stageWidth = 1, stageHeight = stageWidth, { mirrorOk = false } = {}) {
  const seal = NINJA_SEALS[expected];
  const two = ninjaTwoHands(hands);
  if (!seal || !two) return false;
  if (!ninjaPlacementFits(seal.placement, ninjaGap(two, stageWidth, stageHeight))) return false;
  const [first, second] = ninjaOrdered(two, seal.placement);
  if (ninjaShapeFits(first, seal.a) && ninjaShapeFits(second, seal.b)) return true;
  return Boolean(mirrorOk) && ninjaShapeFits(first, seal.b) && ninjaShapeFits(second, seal.a);
}

export function recognizeNinjaSeal(hands, stageWidth = 1, stageHeight = stageWidth) {
  const two = ninjaTwoHands(hands);
  if (!two) return null;
  const placement = ninjaPlacementOf(ninjaGap(two, stageWidth, stageHeight));
  const [first, second] = ninjaOrdered(two, placement);
  const a = ninjaShapeOf(first);
  const b = ninjaShapeOf(second);
  if (!a || !b) return null;
  const id = `${a}-${b}-${placement}`;
  return NINJA_SEALS[id] ? id : null;
}

export function freshNinjaRun(technique = NINJA_DEFAULT_TECHNIQUE, pace = "family") {
  const chosen = ninjaTechnique(technique);
  const speed = MIRROR_PACES[String(pace || "").toLowerCase()]?.id || "family";
  return {
    technique: chosen.id,
    pace: speed,
    index: 0,
    combo: 0,
    bestCombo: 0,
    holdSince: null,
    holdBrokenAt: null,
    evidenceMs: 0,
    lastMatchedAt: null,
    mistakes: 0,
    releaseSince: null,
    stepStartedAt: null,
    awaitRelease: false,
    lastSeal: null,
    finished: false,
    event: "",
  };
}

export function advanceNinjaWeave(run, { seal = null, now = 0 } = {}) {
  const next = { ...freshNinjaRun(run?.technique, run?.pace), ...(run || {}) };
  if (next.finished) return { ...next, event: "done" };
  const technique = ninjaTechnique(next.technique);
  const expected = technique.sequence[next.index];
  if (!Number.isFinite(next.stepStartedAt)) next.stepStartedAt = now;

  if (next.awaitRelease) {
    if (seal === next.lastSeal) {
      next.releaseSince = null;
      return { ...next, event: "release" };
    }
    if (!Number.isFinite(next.releaseSince)) next.releaseSince = now;
    if (now - next.releaseSince < NINJA_RELEASE_MS) return { ...next, event: "release" };
    next.awaitRelease = false;
    next.releaseSince = null;
    next.lastSeal = null;
    next.stepStartedAt = now;
  }

  if (seal !== expected) {
    if (seal) next.mistakes += 1;
    if (Number.isFinite(next.holdSince) && !Number.isFinite(next.holdBrokenAt)) {
      next.holdBrokenAt = now;
    }
    const recentlyMatched = Number.isFinite(next.lastMatchedAt)
      && now - next.lastMatchedAt <= NINJA_HOLD_GRACE_MS;
    return {
      ...next,
      event: recentlyMatched ? "hold" : (seal ? "wrong" : "waiting"),
    };
  }

  const gap = Number.isFinite(next.lastMatchedAt) ? Math.max(0, now - next.lastMatchedAt) : null;
  const credit = gap === null || gap > NINJA_HOLD_GRACE_MS
    ? NINJA_INITIAL_CREDIT_MS
    : Math.min(NINJA_SAMPLE_CAP_MS, gap);
  next.evidenceMs = Math.min(NINJA_HOLD_MS, (Number(next.evidenceMs) || 0) + credit);
  next.lastMatchedAt = now;
  next.holdBrokenAt = null;
  if (!Number.isFinite(next.holdSince)) next.holdSince = now;
  if (next.evidenceMs < NINJA_HOLD_MS) return { ...next, event: "hold" };

  next.index += 1;
  next.combo += 1;
  next.bestCombo = Math.max(next.bestCombo, next.combo);
  next.holdSince = null;
  next.evidenceMs = 0;
  next.lastMatchedAt = null;
  next.mistakes = 0;
  next.stepStartedAt = now;
  next.lastSeal = seal;
  if (next.index >= technique.sequence.length) {
    next.finished = true;
    return { ...next, event: "done" };
  }
  next.awaitRelease = true;
  next.releaseSince = null;
  return { ...next, event: "step" };
}

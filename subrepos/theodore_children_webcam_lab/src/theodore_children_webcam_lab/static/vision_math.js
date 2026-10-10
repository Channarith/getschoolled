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
export function fingerExtended(points, tip, pip) {
  const wrist = points?.[0];
  if (!wrist || !points?.[tip] || !points?.[pip]) return false;
  return (
    distance(points[tip], wrist) >
    distance(points[pip], wrist) + 0.22 * palmSpan(points)
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
    indexUp: fingers[0] && !fingers[1] && !fingers[2] && !fingers[3],
    fist: farthest < FIST_MAX_PALMS,
  };
}

// Coloring only while fingers are out. A closed fist lifts the marker.
export function fingersPointed(shape) {
  return Boolean(shape) && !shape.fist && Number(shape.count) > 0;
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
export const AWAY_HOLD_MS = 2500;
export const RETURN_HOLD_MS = 1200;
export const SIGNAL_HOLD_MS = 1500;
export const BLIND_ARM_MS = 8000;
export const PHONE_PITCH_WITH_GAZE_DEG = 18;
export const PHONE_PITCH_POSE_ONLY_DEG = 28;
export const GAZE_DOWN_MIN = 0.38;
export const YAW_AWAY_DEG = 25;
export const PAUSE_LINE = "I'll pause here. Come back when you're ready.";
export const RESUME_LINE = "Welcome back. We'll continue from the same place.";
export const PHONE_LINE = "Looks like you might be looking down at a phone. The lesson is still here when you look up.";
export const LOOK_AWAY_LINE = "Look back at the screen when you can. I'll keep going from here.";
export const LEFT_LINE = "I can't see you in the camera. I'll wait here.";

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
              line: RESUME_LINE,
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
            line: PAUSE_LINE,
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
          line: PAUSE_LINE,
          notice: LEFT_LINE,
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

// Pop Quiz Toss: pure game logic (no DOM), so it can be tested in Node.
//
// Say the answer out loud AND throw the ball at it. Both right = 5 points, one
// right = 2 points, first to 100 wins. Rounds mirror game_engine.pop_quiz_round().

import {normalizeTouchAge} from "./vision_math.js";

export const GOAL_POINTS = 100;
export const POINTS_BOTH = 5;
export const POINTS_ONE = 2;

// ---- Rounds (must match game_engine.pop_quiz_round) ---------------------------

export function quizBand(age) {
  return normalizeTouchAge(age) || "7-10";
}

export function quizRound(bank, age, index) {
  const slot = Math.max(0, Math.floor(Number(index)) || 0);
  const band = quizBand(age);
  const rows = bank?.[band];
  if (!Array.isArray(rows) || !rows.length) return null;
  const row = rows[slot % rows.length];
  const wrong = row.wrong;
  const distractor = wrong[Math.floor(slot / rows.length) % wrong.length];
  const answer = row.a;
  return {
    round_id: `pop-quiz-${band}-${slot}`,
    index: slot,
    age_band: band,
    question: row.q,
    speak: row.q,
    answer,
    choices: slot % 2 === 0 ? [answer, distractor] : [distractor, answer],
  };
}

// Used only if both the server and the bank file are unreachable.
export const EMERGENCY_BANK = {
  "4-6": [{q: "What color is a banana?", a: "Yellow", wrong: ["Blue"]}, {q: "Which animal says moo?", a: "Cow", wrong: ["Dog"]}],
  "7-10": [{q: "What is the capital of France?", a: "Paris", wrong: ["Rome"]}, {q: "Which planet do we live on?", a: "Earth", wrong: ["Mars"]}],
  "11-17": [{q: "What is the chemical symbol for gold?", a: "Au", wrong: ["Ag"]}, {q: "Which planet is the Red Planet?", a: "Mars", wrong: ["Venus"]}],
  adult: [{q: "What is the capital of Australia?", a: "Canberra", wrong: ["Sydney"]}, {q: "Who wrote 1984?", a: "George Orwell", wrong: ["Aldous Huxley"]}],
};

// ---- Scoring ---------------------------------------------------------------------

/** Both right = 5, exactly one right = 2, neither = 0. */
export function roundPoints({voice, throwHit}) {
  if (voice && throwHit) return POINTS_BOTH;
  return voice || throwHit ? POINTS_ONE : 0;
}

export function nextStreak(streak, points) {
  return points > 0 ? streak + 1 : 0;
}

export function streakTier(streak) {
  if (streak >= 8) return {tier: 3, name: "comet", label: "UNSTOPPABLE!"};
  if (streak >= 5) return {tier: 2, name: "rainbow", label: "ON FIRE!"};
  if (streak >= 3) return {tier: 1, name: "fire", label: "HOT STREAK!"};
  return {tier: 0, name: "plain", label: ""};
}

export function hasWon(points) {
  return points >= GOAL_POINTS;
}

export function starsFor(rounds, points) {
  // More points per round means a cleaner game.
  const per = rounds ? points / rounds : 0;
  return per >= 4 ? 3 : per >= 3 ? 2 : 1;
}

// ---- Voice answers ----------------------------------------------------------------

export function foldText(text) {
  return String(text ?? "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function levenshtein(a, b) {
  const m = a.length;
  const n = b.length;
  if (!m) return n;
  if (!n) return m;
  let prev = Array.from({length: n + 1}, (_, j) => j);
  for (let i = 1; i <= m; i += 1) {
    const cur = [i];
    for (let j = 1; j <= n; j += 1) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[n];
}

function similar(a, b) {
  const longest = Math.max(a.length, b.length);
  return longest ? 1 - levenshtein(a, b) / longest : 0;
}

const NUMBER_WORDS = {
  zero: "0", one: "1", two: "2", three: "3", four: "4", five: "5", six: "6", seven: "7",
  eight: "8", nine: "9", ten: "10", eleven: "11", twelve: "12", sixty: "60",
};

function numberFold(text) {
  return foldText(text).split(" ").map((w) => NUMBER_WORDS[w] ?? w).join(" ");
}

/** Does what was heard contain the answer, allowing small recognition slips? */
export function answerMatches(heard, answer) {
  const target = numberFold(answer);
  const said = numberFold(heard);
  if (!target || !said) return false;
  if (said === target || ` ${said} `.includes(` ${target} `)) return true;
  // "leonardo da vinci" when the answer is "da vinci": every answer word is said.
  const targetWords = target.split(" ");
  const saidWords = said.split(" ");
  if (targetWords.length > 1 && targetWords.every((w) => saidWords.some((s) => similar(s, w) >= 0.8))) return true;
  // Close enough for one word ("canbera"), checked against each word and each pair said.
  const windows = [];
  for (let size = 1; size <= Math.min(2, saidWords.length); size += 1) {
    for (let i = 0; i + size <= saidWords.length; i += 1) windows.push(saidWords.slice(i, i + size).join(" "));
  }
  const need = target.length <= 3 ? 1 : target.length <= 5 ? 0.8 : 0.76;
  return windows.some((w) => similar(w, target) >= need);
}

// ---- Targets and balls ---------------------------------------------------------

export const THEMES = ["dartboard", "pins", "teddy", "bouquet"];
export const BALLS = ["⚽", "🎾", "🏀", "⚾", "🏐", "🏈"];

// Level n unlocks one ball and one target, so there is always something next.
export const LEVEL_POINTS = [0, 150, 400, 800, 1400, 2200];
export const UNLOCKS = [
  {ball: "⚽", theme: "dartboard"},
  {ball: "🎾", theme: "teddy"},
  {ball: "🏀", theme: "pins"},
  {ball: "⚾", theme: "bouquet"},
  {ball: "🏐", theme: null},
  {ball: "🏈", theme: null},
];

export function levelFor(total) {
  let level = 1;
  for (let i = 0; i < LEVEL_POINTS.length; i += 1) if (total >= LEVEL_POINTS[i]) level = i + 1;
  return level;
}

export function unlockedFor(level) {
  const rows = UNLOCKS.slice(0, Math.max(1, Math.min(level, UNLOCKS.length)));
  return {
    balls: rows.map((r) => r.ball),
    themes: rows.map((r) => r.theme).filter(Boolean),
  };
}

export function nextUnlock(total) {
  const level = levelFor(total);
  if (level >= LEVEL_POINTS.length) return null;
  return {at: LEVEL_POINTS[level], remaining: LEVEL_POINTS[level] - total, reward: UNLOCKS[level]};
}

export function themeFor(index, level = 1) {
  const themes = unlockedFor(level).themes;
  return themes[Math.max(0, Math.floor(index)) % themes.length];
}

export function ballFor(index, level = 1) {
  const balls = unlockedFor(level).balls;
  // A different ball most throws, never the same twice in a row.
  return balls[(Math.max(0, Math.floor(index)) * 5 + 1) % balls.length];
}

// ---- Curve balls ---------------------------------------------------------------

const TWO_PI = Math.PI * 2;

/** Signed turning of the fist's path while held: positive = clockwise on screen. */
export function orbitTurn(points) {
  if (!Array.isArray(points) || points.length < 6) return 0;
  const cx = points.reduce((s, p) => s + p.x, 0) / points.length;
  const cy = points.reduce((s, p) => s + p.y, 0) / points.length;
  let total = 0;
  for (let i = 1; i < points.length; i += 1) {
    const a = Math.atan2(points[i - 1].y - cy, points[i - 1].x - cx);
    const b = Math.atan2(points[i].y - cy, points[i].x - cx);
    let d = b - a;
    while (d > Math.PI) d -= TWO_PI;
    while (d < -Math.PI) d += TWO_PI;
    total += d;
  }
  return total;
}

/** How much the last stretch of the throw bends: -1 (left) .. 1 (right). */
export function sweepCurve(history) {
  if (!Array.isArray(history) || history.length < 4) return 0;
  const half = Math.floor(history.length / 2);
  const a = history.slice(0, half + 1);
  const b = history.slice(half);
  const ang = (rows) => {
    const first = rows[0].point;
    const last = rows[rows.length - 1].point;
    return Math.atan2(last.y - first.y, last.x - first.x);
  };
  let d = ang(b) - ang(a);
  while (d > Math.PI) d -= TWO_PI;
  while (d < -Math.PI) d += TWO_PI;
  return Math.max(-1, Math.min(1, d / (Math.PI / 3)));
}

/** A spin before the throw (a full swirl) or a swinging arc both make a curve ball. */
export function throwCurve(release, spinRadians = 1.5 * Math.PI) {
  const spin = orbitTurn((release?.orbit || []).map((p) => ({x: p.x, y: p.y})));
  if (Math.abs(spin) >= spinRadians) return {curve: spin > 0 ? 1 : -1, kind: "spin"};
  const sweep = sweepCurve(release?.history || []);
  if (Math.abs(sweep) >= 0.45) return {curve: sweep, kind: "sweep"};
  return {curve: 0, kind: "none"};
}

// ---- Resolving a throw: generous on purpose -------------------------------------------

const CURVE_BEND = 0.4;

/**
 * Pick the target a throw is going to. Close counts: the nearest target to where
 * the (curved) throw is heading wins, unless the throw points away from every
 * target. Returns {target, miss, curve, kind, accuracy, end, control}.
 */
export function resolveThrow(release, targets, tolerance = 2.4) {
  const velocity = release?.velocity;
  const origin = release?.origin;
  const speed = Math.hypot(Number(velocity?.x) || 0, Number(velocity?.y) || 0);
  const list = (Array.isArray(targets) ? targets : []).filter((t) => Number.isFinite(t?.x) && Number.isFinite(t?.y));
  if (!origin || speed <= 0 || !list.length) return {target: null, miss: true, curve: 0, kind: "none", accuracy: 0};
  const dir = {x: velocity.x / speed, y: velocity.y / speed};
  const perp = {x: -dir.y, y: dir.x};
  const {curve, kind} = throwCurve(release);
  let best = null;
  for (const target of list) {
    const dx = target.x - origin.x;
    const dy = target.y - origin.y;
    const dist = Math.max(1, Math.hypot(dx, dy));
    const cosine = (dx * dir.x + dy * dir.y) / dist;
    if (cosine < -0.15) continue;
    const lateral = curve * CURVE_BEND * dist;
    const curved = {x: origin.x + dir.x * dist + perp.x * lateral, y: origin.y + dir.y * dist + perp.y 
      * lateral};
    const straight = {x: origin.x + dir.x * dist, y: origin.y + dir.y * dist};
    const radius = Math.max(1, Number(target.radius) || 64);
    // Generous: a curve ball counts if EITHER the straight line or the bent path
    // ends near the answer, so a spin never turns a good aim into a miss.
    const straightError = Math.hypot(target.x - straight.x, target.y - straight.y) / radius;
    const curvedError = Math.hypot(target.x - curved.x, target.y - curved.y) / radius;
    const error = Math.min(straightError, curvedError);
    if (!best || error < best.error) best = {target, error, dist, lateral, curvedBetter: curvedError < straightError};
  }
  if (!best) return {target: null, miss: true, curve, kind, accuracy: 0};
  const accuracy = Math.max(0, Math.min(1, 1 - best.error / tolerance));
  const mid = {x: (origin.x + best.target.x) / 2, y: (origin.y + best.target.y) / 2};
  return {
    target: best.target,
    miss: false,
    curve,
    kind,
    accuracy,
    perfect: best.error <= 0.9,
    end: {x: best.target.x, y: best.target.y},
    control: curve ? {x: mid.x + perp.x * best.lateral * (best.curvedBetter ? 1.4 : 0.7), y: mid.y + perp.y * best.lateral * (best.curvedBetter ? 1.4 : 0.7)} : mid,
  };
}

/** A point along a quadratic curve, t in 0..1. */
export function curvePoint(start, control, end, t) {
  const u = 1 - t;
  return {
    x: u * u * start.x + 2 * u * t * control.x + t * t * end.x,
    y: u * u * start.y + 2 * u * t * control.y + t * t * end.y,
  };
}

// ---- Coaching: stay in the picture, right distance ---------------------------------------

/**
 * One short hint when the hand is hard to see, or null when all is well.
 * palmFraction is the palm span as a fraction of the shorter side of the stage.
 */
export function coachHint({seen, msSinceSeen = 0, wrist = null, palmFraction = 0}) {
  if (!seen) return msSinceSeen > 2200 ? "no-hand" : null;
  if (wrist) {
    const edge = 0.07;
    if (wrist.x < edge || wrist.x > 1 - edge || wrist.y < edge || wrist.y > 1 - edge) return "edge";
  }
  if (palmFraction > 0 && palmFraction < 0.05) return "far";
  if (palmFraction > 0.3) return "close";
  return null;
}

export const COACH_TEXT = {
  "no-hand": "I can't see your hand. Step into the picture and show your fist.",
  edge: "Your hand is leaving the picture. Move it toward the middle.",
  far: "Step a little closer so I can see your hand.",
  close: "Step back a little so your whole arm fits in the picture.",
};

// ---- Progress kept on this device ---------------------------------------------------------

export const PROGRESS_KEY = "pop_quiz_progress_v1";
export const TUTORIAL_KEY = "pop_quiz_tutorial_seen_v1";

export function loadProgress(storage) {
  try {
    const raw = JSON.parse(storage?.getItem(PROGRESS_KEY) || "{}");
    return {
      total: Math.max(0, Number(raw.total) || 0),
      best: Math.max(0, Number(raw.best) || 0),
      bestStreak: Math.max(0, Number(raw.bestStreak) || 0),
      wins: Math.max(0, Number(raw.wins) || 0),
    };
  } catch (_) {
    return {total: 0, best: 0, bestStreak: 0, wins: 0};
  }
}

export function saveProgress(storage, progress) {
  try {
    storage?.setItem(PROGRESS_KEY, JSON.stringify(progress));
  } catch (_) {
    // Private browsing: progress just will not be kept.
  }
}

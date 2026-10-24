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

// ---- Resolving a throw: generous on purpose -------------------------------------------

/**
 * Pick the target a throw is going to. Close counts: the nearest target to where
 * the throw is heading wins, unless the throw points away from every target.
 * Straight lines only. Returns {target, miss, accuracy, perfect, end}.
 */
export function resolveThrow(release, targets, tolerance = 2.4) {
  const velocity = release?.velocity;
  const origin = release?.origin;
  const speed = Math.hypot(Number(velocity?.x) || 0, Number(velocity?.y) || 0);
  const list = (Array.isArray(targets) ? targets : []).filter((t) => Number.isFinite(t?.x) && Number.isFinite(t?.y));
  if (!origin || speed <= 0 || !list.length) return {target: null, miss: true, accuracy: 0};
  const dir = {x: velocity.x / speed, y: velocity.y / speed};
  let best = null;
  for (const target of list) {
    const dx = target.x - origin.x;
    const dy = target.y - origin.y;
    const dist = Math.max(1, Math.hypot(dx, dy));
    const cosine = (dx * dir.x + dy * dir.y) / dist;
    if (cosine < -0.15) continue;
    const radius = Math.max(1, Number(target.radius) || 64);
    const error = Math.hypot(target.x - (origin.x + dir.x * dist), target.y - (origin.y + dir.y * dist)) / radius;
    if (!best || error < best.error) best = {target, error};
  }
  if (!best) return {target: null, miss: true, accuracy: 0};
  return {
    target: best.target,
    miss: false,
    accuracy: Math.max(0, Math.min(1, 1 - best.error / tolerance)),
    perfect: best.error <= 0.9,
    end: {x: best.target.x, y: best.target.y},
  };
}

// ---- Which hand throws picks the answer ----------------------------------------------------
//
// The LEFT hand throws at the LEFT answer and the RIGHT hand at the RIGHT answer. MediaPipe reports
// handedness as if the picture were already a mirror, but the lab feeds it the raw camera frame and
// only mirrors it for display, so its label is swapped: "Left" is the player's RIGHT hand.
export const HANDEDNESS_FLIPPED = true;

function labelSide(label) {
  const raw = String(label || "").trim().toLowerCase();
  if (raw !== "left" && raw !== "right") return null;
  return HANDEDNESS_FLIPPED ? (raw === "left" ? "right" : "left") : raw;
}

/**
 * Which hand is this, from the player's point of view? `hand.wrist.x` is in the mirrored stage
 * (what the player sees), so a hand far in the left third of the screen is the left hand. In the
 * middle band the handedness label decides, and without a label the half of the screen does.
 */
export function playerHandSide(hand, width) {
  const w = Number(width) || 0;
  const x = Number(hand?.wrist?.x);
  const frac = w > 0 && Number.isFinite(x) ? x / w : null;
  if (frac !== null && (hand?.screen || frac < 0.38)) return frac < 0.5 ? "left" : "right";
  if (frac !== null && frac > 0.62) return "right";
  return labelSide(hand?.label) || (frac !== null ? (frac < 0.5 ? "left" : "right") : null);
}

/**
 * Give every visible hand a side. With two hands the one further left on screen is the left hand
 * (they cannot both be the same hand); with one hand `playerHandSide` decides.
 */
export function assignHandSides(hands, width) {
  const list = (Array.isArray(hands) ? hands : []).filter((h) => h?.wrist);
  if (list.length >= 2) {
    const sorted = [...list].sort((a, b) => a.wrist.x - b.wrist.x);
    const left = sorted[0];
    const right = sorted[sorted.length - 1];
    if (Math.abs(right.wrist.x - left.wrist.x) >= 0.08 * (Number(width) || 1)) {
      return [{hand: left, side: "left"}, {hand: right, side: "right"}];
    }
  }
  return list.map((hand) => ({hand, side: playerHandSide(hand, width)}));
}

/** The leftmost target is the left answer, the rightmost is the right answer. */
export function targetForSide(side, targets) {
  const list = (Array.isArray(targets) ? targets : []).filter((t) => Number.isFinite(t?.x));
  if (!list.length || (side !== "left" && side !== "right")) return null;
  return [...list].sort((a, b) => a.x - b.x)[side === "left" ? 0 : list.length - 1];
}

/**
 * Touch, mouse and screen-touch throws have no hand: the swipe direction (or, for a still tap,
 * the half of the screen it started in) picks the side.
 */
export function sideFromRelease(release, width) {
  if (release?.side === "left" || release?.side === "right") return release.side;
  const vx = Number(release?.velocity?.x) || 0;
  const vy = Number(release?.velocity?.y) || 0;
  if (vx !== 0 && Math.abs(vx) > 0.2 * Math.abs(vy)) return vx < 0 ? "left" : "right";
  const x = Number(release?.origin?.x);
  return Number.isFinite(x) && Number(width) > 0 ? (x < Number(width) / 2 ? "left" : "right") : null;
}

// ---- Assisted throws ---------------------------------------------------------------------------

export const ASSIST_RATE = 0.9;

export function clampAssistRate(value, fallback = ASSIST_RATE) {
  if (value === null || value === undefined || value === "") return fallback;
  const n = Number(value);
  return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : fallback;
}

/**
 * Decide where a released ball lands. About 90% of throws are steered onto the answer the PLAYER
 * CHOSE with their hand (or swipe); the rest use the real motion (resolveThrow), which can hit
 * either answer or miss.
 *
 * Integrity: this function never sees the correct answer. It can only pick between the two
 * targets by side, so the assist can never steer a throw to the right answer on the player's
 * behalf. Scoring still compares the chosen answer with the correct one.
 */
export function resolveAssistedThrow(release, targets, {width = 0, rate = ASSIST_RATE, rng = Math.random, tolerance} = {}) {
  const side = sideFromRelease(release, width);
  const chosen = targetForSide(side, targets);
  if (chosen && rng() < clampAssistRate(rate)) {
    return {
      target: chosen, miss: false, accuracy: 1, perfect: false, assisted: true, side,
      end: {x: chosen.x, y: chosen.y},
    };
  }
  const natural = resolveThrow(release, targets, tolerance);
  return {...natural, assisted: false, side};
}

// ---- Time to answer -----------------------------------------------------------------------------

export const MIN_QUESTION_SECONDS = 10;
export const QUESTION_SECONDS = 12;
export const YOUNG_QUESTION_SECONDS = 15;

/** Seconds to answer: never under 10; the youngest band gets more room. */
export function questionSeconds(age, override) {
  const base = quizBand(age) === "4-6" ? YOUNG_QUESTION_SECONDS : QUESTION_SECONDS;
  const n = override === undefined || override === null || override === "" ? NaN : Number(override);
  const value = Number.isFinite(n) ? n : base;
  return Math.max(MIN_QUESTION_SECONDS, Math.min(60, value));
}

/**
 * A pausable countdown. The caller says when it is paused (tutorial open, ball in the air, the
 * player is speaking); a long gap between ticks (hidden tab) never burns more than 250 ms.
 */
export function createQuestionTimer(seconds) {
  const totalMs = Math.max(MIN_QUESTION_SECONDS, Number(seconds) || QUESTION_SECONDS) * 1000;
  let remaining = totalMs;
  let last = null;
  const snap = () => ({remainingMs: remaining, fraction: remaining / totalMs, seconds: Math.ceil(remaining / 1000), expired: remaining <= 0});
  return {
    totalMs,
    start(now) { remaining = totalMs; last = now; return snap(); },
    tick(now, paused = false) {
      if (last === null) { last = now; return snap(); }
      const dt = Math.max(0, Math.min(250, now - last));
      last = now;
      if (!paused) remaining = Math.max(0, remaining - dt);
      return snap();
    },
    /** Make sure at least `ms` are left (a window to say the answer after a throw). */
    ensureRemaining(ms) { remaining = Math.min(totalMs, Math.max(remaining, ms)); return snap(); },
    state: snap,
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

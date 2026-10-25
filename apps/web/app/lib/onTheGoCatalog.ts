/** On the Go: curated demo courses, per-course resume points, spoken course commands and a question limiter. Pure logic, no React. */

export type CourseLike = { id: string; title: string; category?: string; duration_min?: number; level?: string };

/** Public demo courses (all exist in the audio catalog). The first is the default. Signed-in users see the full catalog. */
export const DEMO_COURSE_IDS: readonly string[] = [
  "audio-intro-to-machine-learning",
  "audio-what-is-artificial-intelligence",
  "audio-cybersecurity-basics",
  "audio-the-roman-empire",
  "audio-climate-and-weather",
  "audio-understanding-classical-music",
];

export const DEMO_PICKER_FLAG = "on_the_go.demo_course_picker";
/** Demo: search the whole pre-translated catalog instead of the 6 curated courses (default off: sign-in is required beyond the demo). */
export const DEMO_FULL_SEARCH_FLAG = "on_the_go.demo_full_search";
export const INCLUDE_ENGLISH_KEY = "salareen.onTheGo.includeEnglish";

/** Keep only the curated courses the catalog actually returned, in curated order. */
export function curatedRows<T extends { id: string }>(rows: T[], ids: readonly string[] = DEMO_COURSE_IDS): T[] {
  const byId = new Map(rows.map((r) => [r.id, r]));
  const out: T[] = [];
  for (const id of ids) {
    const row = byId.get(id);
    if (row) out.push(row);
  }
  return out;
}

export function cleanTitle(title: string): string {
  return (title || "").replace(/\s*\(audio\)\s*$/i, "").trim();
}

// ---- resume points ------------------------------------------------------- //

export type Progress = { lastCourseId: string; courses: Record<string, { seg: number; at: number }> };
export const PROGRESS_KEY = "salareen.onTheGo.progress.v1";
const MAX_REMEMBERED = 60;

type StorageLike = { getItem(k: string): string | null; setItem(k: string, v: string): void };

function browserStorage(): StorageLike | null {
  try {
    const s = (globalThis as { localStorage?: StorageLike }).localStorage;
    return s ?? null;
  } catch {
    return null; // private mode / blocked storage
  }
}

export function readProgress(storage: StorageLike | null = browserStorage()): Progress {
  const empty: Progress = { lastCourseId: "", courses: {} };
  if (!storage) return empty;
  try {
    const raw = storage.getItem(PROGRESS_KEY);
    if (!raw) return empty;
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object" || typeof data.courses !== "object" || data.courses === null) return empty;
    const courses: Progress["courses"] = {};
    for (const [id, v] of Object.entries(data.courses as Record<string, { seg?: unknown; at?: unknown }>)) {
      const seg = Number(v?.seg);
      if (Number.isInteger(seg) && seg >= 0 && seg < 10000) courses[id] = { seg, at: Number(v?.at) || 0 };
    }
    return { lastCourseId: typeof data.lastCourseId === "string" ? data.lastCourseId : "", courses };
  } catch {
    return empty;
  }
}

export function saveProgress(courseId: string, seg: number, storage: StorageLike | null = browserStorage(), now: number = Date.now()): void {
  if (!storage || !courseId || !Number.isInteger(seg) || seg < 0) return;
  const cur = readProgress(storage);
  cur.courses[courseId] = { seg, at: now };
  cur.lastCourseId = courseId;
  const ids = Object.keys(cur.courses);
  if (ids.length > MAX_REMEMBERED) {
    ids.sort((a, b) => cur.courses[a].at - cur.courses[b].at);
    for (const id of ids.slice(0, ids.length - MAX_REMEMBERED)) delete cur.courses[id];
  }
  try { storage.setItem(PROGRESS_KEY, JSON.stringify(cur)); } catch { /* quota / private mode */ }
}

/** Where to restart a course: the saved segment, unless it is out of range or the course was finished. */
export function resumeSegment(progress: Progress, courseId: string, segmentCount: number): number {
  const saved = progress.courses[courseId]?.seg;
  if (saved === undefined || segmentCount <= 0) return 0;
  return saved >= 0 && saved < segmentCount ? saved : 0;
}

// ---- spoken course commands ---------------------------------------------- //

export type CourseCommand =
  | { kind: "play"; id: string }
  | { kind: "next" }
  | { kind: "previous" }
  | { kind: "list" }
  | { kind: "unknown"; wanted: string };

const STOP_WORDS = new Set([
  "a", "an", "the", "of", "on", "to", "and", "about", "course", "class", "lesson", "audio", "please", "me", "for", "in",
  "my", "some", "is", "what", "how", "history", "intro", "introduction",
]);

function tokens(text: string): string[] {
  return (text || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function contentTokens(text: string): string[] {
  const all = tokens(text);
  const kept = all.filter((w) => !STOP_WORDS.has(w));
  return kept.length ? kept : all;
}

/** Best title match for what was said, or null. A match needs every spoken content word to appear in the title (prefix-tolerant). */
export function matchCourse<T extends CourseLike>(spoken: string, rows: T[]): T | null {
  const want = contentTokens(spoken);
  if (!want.length) return null;
  let best: { row: T; score: number } | null = null;
  for (const row of rows) {
    const have = contentTokens(cleanTitle(row.title));
    const hits = want.filter((w) => have.some((h) => h === w || (w.length >= 4 && (h.startsWith(w) || w.startsWith(h) && h.length >= 4)))).length;
    if (hits < want.length) continue;
    const score = hits * 10 - Math.abs(have.length - want.length);
    if (!best || score > best.score) best = { row, score };
  }
  return best ? best.row : null;
}

const PLAY_VERBS = /^(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?(?:play|start|begin|open|switch\s+to|change\s+to|go\s+to|put\s+on|i\s+want\s+to\s+(?:hear|listen\s+to)|let'?s\s+(?:hear|listen\s+to))\s+(.+)$/i;

/** Course-level voice commands. Returns null for anything else (playback commands and questions go elsewhere). */
export function parseCourseCommand<T extends CourseLike>(text: string, rows: T[], currentId = ""): CourseCommand | null {
  const raw = (text || "").trim().replace(/[.!?]+$/g, "");
  if (!raw) return null;
  const lower = raw.toLowerCase();
  if (/^(?:play\s+|go\s+to\s+|switch\s+to\s+|skip\s+to\s+)?(?:the\s+)?next\s+(?:course|class|lesson topic|topic)$/.test(lower)) return { kind: "next" };
  if (/^(?:play\s+|go\s+to\s+|switch\s+to\s+|go\s+back\s+to\s+)?(?:the\s+)?(?:previous|last)\s+(?:course|class|topic)$/.test(lower)) return { kind: "previous" };
  if (/^(?:play\s+)?(?:another|a\s+different|some\s+other)\s+(?:course|class|topic)$/.test(lower)) return { kind: "next" };
  if (/^(?:what|which)\s+(?:courses|classes|topics)(?:\s+.*)?$/.test(lower) || /^(?:list|show)\s+(?:the\s+|all\s+)?(?:courses|classes|topics)$/.test(lower)) return { kind: "list" };
  const m = PLAY_VERBS.exec(raw);
  if (!m) return null;
  let target = m[1].trim();
  // "play the roman empire course", "play that" etc.: only course-ish requests, not "play faster".
  if (/^(?:it|that|this|them|again|faster|slower|more|on|back|from\b.*|the\s+(?:lesson|audio|course|class)|(?:it|that|this)\s+.*|.*\s+(?:again|faster|slower))$/i.test(target)) return null;
  target = target.replace(/\b(?:course|class)\b\s*$/i, "").trim();
  if (!target) return null;
  const hit = matchCourse(target, rows.filter((r) => r.id !== currentId).concat(rows.filter((r) => r.id === currentId)));
  return hit ? { kind: "play", id: hit.id } : { kind: "unknown", wanted: target };
}

/** Neighbour of the current course in the list (wraps around). */
export function neighbourCourse<T extends { id: string }>(rows: T[], currentId: string, step: 1 | -1): T | null {
  if (!rows.length) return null;
  const idx = rows.findIndex((r) => r.id === currentId);
  const next = idx === -1 ? (step === 1 ? 0 : rows.length - 1) : (idx + step + rows.length) % rows.length;
  return rows[next] ?? null;
}

// ---- question limiter ----------------------------------------------------- //

export type LimitResult = { ok: true } | { ok: false; reason: "rate" | "session"; retryAfterS: number };

/** Cheap guard for spoken questions: a burst limit and a per-session cap, so a noisy room cannot run up TTS or model calls. */
export class QuestionLimiter {
  private times: number[] = [];
  private total = 0;
  private readonly perMinute: number;
  private readonly perSession: number;
  private readonly now: () => number;

  constructor(perMinute = 6, perSession = 40, now: () => number = () => Date.now()) {
    this.perMinute = perMinute;
    this.perSession = perSession;
    this.now = now;
  }

  check(): LimitResult {
    const t = this.now();
    this.times = this.times.filter((x) => t - x < 60_000);
    if (this.total >= this.perSession) return { ok: false, reason: "session", retryAfterS: 0 };
    if (this.times.length >= this.perMinute) {
      return { ok: false, reason: "rate", retryAfterS: Math.max(1, Math.ceil((60_000 - (t - this.times[0])) / 1000)) };
    }
    this.times.push(t);
    this.total += 1;
    return { ok: true };
  }

  reset(): void { this.times = []; this.total = 0; }
}

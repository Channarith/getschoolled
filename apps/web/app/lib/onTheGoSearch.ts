/**
 * On the Go course search: fuzzy matching, ranking (courses ready in the voice's language first), the spoken "search for ..." command
 * and list windowing for the big catalog. Pure logic with no imports, so the unit tests load this file as is.
 */

export type SearchRow = {
  id: string;
  title: string;
  title_local?: string;
  category?: string;
  subject?: string;
  level?: string;
  duration_min?: number;
  tags?: string[];
  segments?: number;
  /** Languages with a shippable translation (server verdict). */
  ready_languages?: string[];
  /** Ready in the language the search was made for. */
  ready?: boolean;
  english_only?: boolean;
  /** A topic the catalog defines but has no course for yet: found by search, shown as "coming soon", not playable. */
  planned?: boolean;
};

export type SearchOptions = {
  /** Language family of the voice ("en", "es", "yue", ...). */
  language: string;
  /** false hides courses that are not ready in `language`. */
  includeEnglish: boolean;
  /** Demo allowlist: only these ids are searchable (omit for the full catalog). */
  allowedIds?: readonly string[];
  /** Groups of equivalent terms from the server ("machine vision" = "computer vision"): a query that equals or starts a term also finds the others. */
  aliases?: readonly (readonly string[])[];
};

/** Lowercase, accent-free, punctuation-free; keeps letters and numbers of every script. */
export function fold(text: string): string {
  return (text || "")
    .normalize("NFKD")
    .replace(/\p{M}+/gu, "")
    .toLowerCase()
    .replace(/\(audio\)|（音频）/g, " ")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const UNSPACED = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}\p{Script=Thai}\p{Script=Khmer}\p{Script=Lao}\p{Script=Myanmar}]/u;

/** Is the edit distance between a and b at most `max`? (bounded, so long strings stay cheap). */
export function withinEdits(a: string, b: string, max: number): boolean {
  if (a === b) return true;
  if (Math.abs(a.length - b.length) > max) return false;
  const m = a.length;
  const n = b.length;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i += 1) {
    const cur = [i];
    let best = i;
    for (let j = 1; j <= n; j += 1) {
      const v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      cur.push(v);
      if (v < best) best = v;
    }
    if (best > max) return false;
    prev = cur;
  }
  return prev[n] <= max;
}

/** How well one query word matches one word of the text (0 = no match). */
export function tokenScore(q: string, h: string): number {
  if (!q || !h) return 0;
  if (q === h) return 3;
  if (q.length >= 2 && h.startsWith(q)) return 2.5;
  if (q.length >= 3 && h.includes(q)) return 2;
  if (q.length >= 4 && withinEdits(q, h, q.length >= 8 ? 2 : 1)) return 1.5;
  if (q.length >= 5 && h.length >= 5 && withinEdits(q, h.slice(0, q.length), 1)) return 1.2;   // a typo inside a longer word
  return 0;
}

/** Fuzzy score of a query against a text: every query word must match some word (0 when one does not). */
export function fuzzyScore(query: string, text: string): number {
  const q = fold(query);
  const t = fold(text);
  if (!q || !t) return 0;
  if (UNSPACED.test(q)) return t.replace(/\s/g, "").includes(q.replace(/\s/g, "")) ? 2 + q.length / 10 : 0;
  const qw = q.split(" ");
  const tw = t.split(" ");
  let total = 0;
  for (const word of qw) {
    let best = 0;
    for (const h of tw) {
      const s = tokenScore(word, h);
      if (s > best) best = s;
    }
    if (best === 0) return 0;
    total += best;
  }
  if (t.includes(q)) total += 2;          // the whole phrase appears
  if (t.startsWith(q)) total += 1;
  return total;
}

function rowText(row: SearchRow): { title: string; other: string } {
  return {
    title: `${row.title_local || ""} ${row.title || ""}`,
    other: `${row.category || ""} ${row.subject || ""} ${(row.tags || []).join(" ")}`,
  };
}

/** Other terms to look for when the query equals, or starts, a term of an alias group ("cp" -> "cpr" -> "first aid"). */
export function aliasTerms(query: string, groups?: readonly (readonly string[])[]): string[] {
  const q = fold(query);
  if (!groups || q.length < 2) return [];
  const out: string[] = [];
  for (const g of groups) {
    const terms = g.map(fold).filter(Boolean);
    if (terms.some((t) => t === q || t.startsWith(q))) for (const t of terms) if (!out.includes(t)) out.push(t);
  }
  return out;
}

/** A short term ("ai", "ml") must be a whole word, so it does not match inside "training". */
function altIn(alt: string, text: string): boolean {
  const t = fold(text);
  return alt.length < 4 ? t.split(" ").includes(alt) : t.includes(alt);
}

/** Does the query start a word of the text, with a 2-letter minimum ("cp" starts "cpr")? Used for short queries that must not match inside words. */
function startsWord(query: string, text: string): boolean {
  const qw = fold(query).split(" ").filter(Boolean);
  const tw = fold(text).split(" ");
  return qw.length > 0 && qw.every((x) => tw.some((w) => w.startsWith(x)));
}

export function isReadyIn(row: SearchRow, language: string): boolean {
  if (row.planned) return false;
  if (!language || language === "en") return true;
  if (typeof row.ready === "boolean") return row.ready;
  return Boolean(row.ready_languages && row.ready_languages.includes(language));
}

/**
 * Filter and rank the catalog for a query. Courses ready in the voice's language come first, then by match quality, then by title.
 * `allowedIds` limits the list (the anonymous demo's curated set) in the catalog's own order.
 */
export function rankCourses<T extends SearchRow>(rows: readonly T[], query: string, opts: SearchOptions): T[] {
  const allowed = opts.allowedIds ? new Set(opts.allowedIds) : null;
  const language = opts.language || "en";
  const needle = fold(query);
  const pool = rows.filter((r) => (!allowed || allowed.has(r.id)) && (opts.includeEnglish || isReadyIn(r, language)) && (!r.planned || (needle && !allowed)));
  if (!needle) {
    // No query: ready-in-language first, otherwise the catalog's (or the curated) order.
    return pool.map((r, i) => ({ r, i, ready: isReadyIn(r, language) }))
      .sort((a, b) => (a.ready === b.ready ? a.i - b.i : a.ready ? -1 : 1)).map((x) => x.r);
  }
  const scored: { r: T; score: number; ready: boolean; planned: boolean; title: string }[] = [];
  const alts = aliasTerms(needle, opts.aliases).filter((a) => a !== needle);
  for (const r of pool) {
    const { title, other } = rowText(r);
    let score = Math.max(fuzzyScore(needle, title) * 1.0, fuzzyScore(needle, other) * 0.6);
    // A one- or two-letter query may start a word but not hide inside one ("ai" inside "explained").
    if (needle.length < 3 && !startsWord(needle, title) && !startsWord(needle, other)) score = 0;
    if (score === 0 && alts.length) {
      const hit = alts.some((a) => altIn(a, title) || altIn(a, other));
      if (hit) score = 0.5;   // found through a synonym: below every direct match
    }
    if (score > 0) scored.push({ r, score, ready: isReadyIn(r, language), planned: Boolean(r.planned), title: fold(r.title_local || r.title) });
  }
  // Real courses first (ready in the voice's language, then the rest), "coming soon" topics last; then by match quality and title.
  scored.sort((a, b) => (a.planned !== b.planned ? (a.planned ? 1 : -1) : a.ready !== b.ready ? (a.ready ? -1 : 1) : b.score - a.score || a.title.localeCompare(b.title)));
  return scored.map((x) => x.r);
}

export type Badge = { kind: "ready" | "other" | "english-only"; languages: string[] };

/** What to show on a row: ready in the voice's language, ready only in other languages, or English only. */
export function badgeFor(row: SearchRow, language: string): Badge {
  const langs = row.ready_languages || [];
  if (!language || language === "en") return { kind: "ready", languages: ["en"] };
  if (isReadyIn(row, language)) return { kind: "ready", languages: [language] };
  return langs.length ? { kind: "other", languages: langs.slice(0, 3) } : { kind: "english-only", languages: [] };
}

// ---- spoken search ------------------------------------------------------- //

export type SearchCommand = { kind: "search"; query: string } | { kind: "clear" };

const SEARCH_FOR = /^(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?(?:search(?:\s+(?:for|the\s+courses\s+for|courses\s+for))?|find(?:\s+me)?(?:\s+(?:a|an|some|the))?(?:\s+(?:course|courses|class|classes))?(?:\s+(?:on|about|for))?|look\s+for|look\s+up|browse|show\s+me\s+(?:courses|classes)\s+(?:on|about))\s+(.+)$/i;

/** "search for the roman empire", "find me a course on black holes". null for anything else (play commands and questions go elsewhere). */
export function parseSearchCommand(text: string): SearchCommand | null {
  const raw = (text || "").trim().replace(/[.!?]+$/g, "");
  if (!raw) return null;
  if (/^(?:clear|reset)\s+(?:the\s+)?search$/i.test(raw) || /^show\s+(?:me\s+)?(?:all|every)\s+(?:the\s+)?courses$/i.test(raw)) return { kind: "clear" };
  const m = SEARCH_FOR.exec(raw);
  if (!m) return null;
  const query = m[1].replace(/\b(?:course|courses|class|classes)\b\s*$/i, "").trim();
  if (!query || query.split(/\s+/).length > 8) return null;   // a long sentence is a question, not a search
  return { kind: "search", query };
}

// ---- list windowing (the full catalog is hundreds of rows) --------------- //

export type Windowed = { start: number; end: number; padTop: number; padBottom: number };

/** Which rows to render for a scroll position (fixed row height), with a little overscan on both sides. */
export function windowRows(count: number, scrollTop: number, viewport: number, rowHeight: number, overscan = 4): Windowed {
  const total = Math.max(0, Math.floor(count));
  if (total === 0 || rowHeight <= 0) return { start: 0, end: 0, padTop: 0, padBottom: 0 };
  const view = Math.max(0, viewport);
  const top = Math.min(Math.max(0, scrollTop), Math.max(0, total * rowHeight - view));   // a scroll position past the end is the end
  const first = Math.max(0, Math.floor(top / rowHeight) - overscan);
  const end = Math.min(total, Math.ceil((top + view) / rowHeight) + overscan);
  return { start: first, end, padTop: first * rowHeight, padBottom: (total - end) * rowHeight };
}

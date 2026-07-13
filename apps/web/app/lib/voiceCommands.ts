// Pure parsing for Drive Mode hands-free voice.
//
// Drive Mode keeps the mic ALWAYS listening (no button). To avoid the spoken
// narration (which the mic also hears) triggering false questions, we act only
// on utterances that contain the wake word ("Hey Sala" / "Salareen" / "Sala").
// Once activated we treat the rest of the utterance — or the next one — as a
// command or a question. This module is pure so it can be unit-tested.

export type DriveCommand =
  | { kind: "pause" }
  | { kind: "resume" }
  | { kind: "next" }
  | { kind: "previous" }
  | { kind: "repeat" }
  | { kind: "question"; text: string }
  | { kind: "none" };

// Wake word: "hey sala", "hey salareen", "salareen", or bare "sala".
const WAKE_RE = /\b(hey\s+sala(?:reen)?|salareen|sala)\b/i;

export function hasWakeWord(text: string): boolean {
  return WAKE_RE.test(text || "");
}

export function stripWakeWords(text: string): string {
  return (text || "")
    .replace(/\bhey\s+sala(?:reen)?\b/gi, "")
    .replace(/\bsalareen\b/gi, "")
    .replace(/\bsala\b/gi, "")
    .trim();
}

/**
 * If `text` contains the wake word, return the content AFTER it (may be empty
 * when the caller just said the wake word). Returns null when no wake word.
 */
export function extractAfterWake(text: string): string | null {
  const t = text || "";
  const m = WAKE_RE.exec(t);
  if (!m) return null;
  return t.slice(m.index + m[0].length).replace(/^[\s,.:;!?-]+/, "").trim();
}

// Interrogatives that start a real question.
const QUESTION_STARTERS =
  /^(what'?s?|why|how|when|where|who|whom|whose|which|can|could|would|will|do|does|did|is|are|am|should|shall|may|might|have|has|had|explain|define|describe|tell me|help me|i (?:don'?t|do not) (?:understand|get))\b/i;

/**
 * Is this utterance an actual QUESTION (vs a statement, filler, or noise)?
 * Used by always-listen mode to pause the course ONLY for questions.
 */
export function isQuestion(text: string): boolean {
  const t = (text || "").trim();
  if (!t) return false;
  if (t.endsWith("?")) return true;
  const words = t.split(/\s+/).filter(Boolean);
  if (words.length < 2) return false;                       // single-word blips = noise
  if (QUESTION_STARTERS.test(t)) return true;
  return /\b(what|why|how|explain|meaning of|difference between|what does|how do|how does)\b/i.test(t);
}

function normalizeWords(text: string): string[] {
  return (text || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean);
}

/**
 * Is the heard text most likely the spoken narration the mic picked up (echo),
 * rather than the user? True when the heard words overlap heavily with the
 * currently-narrated text — so the narration's own rhetorical questions don't
 * pause the course.
 */
export function isLikelyEcho(heard: string, narration: string): boolean {
  const h = normalizeWords(heard);
  if (h.length < 2) return false;
  const narrationSet = new Set(normalizeWords(narration));
  if (narrationSet.size === 0) return false;
  const overlap = h.filter((w) => narrationSet.has(w)).length / h.length;
  return overlap >= 0.6;
}

/** Classify a (wake-word-stripped) utterance into a command or a question. */
export function classifyCommand(text: string): DriveCommand {
  const lower = (text || "").toLowerCase().trim();
  if (!lower) return { kind: "none" };
  if (/\b(pause|stop|hold on|be quiet|quiet|shush|wait)\b/.test(lower)) return { kind: "pause" };
  if (/\b(resume|continue|carry on|keep going|unpause|play)\b/.test(lower)) return { kind: "resume" };
  if (/\b(next|skip(?:\s+ahead)?|move on|forward)\b/.test(lower)) return { kind: "next" };
  if (/\b(previous|go back|back up|last one|rewind)\b/.test(lower)) return { kind: "previous" };
  if (/\b(repeat|say that again|again|come again|one more time)\b/.test(lower)) return { kind: "repeat" };
  return { kind: "question", text: (text || "").trim() };
}

export type WakeParse = {
  /** The wake word was heard in this utterance. */
  activated: boolean;
  /** A command/question was present after the wake word (else await the next utterance). */
  command: DriveCommand;
};

/**
 * Parse an ambient final transcript while WAITING for the wake word.
 * - No wake word -> ignored (activated=false).
 * - Wake word only -> activated, command "none" (caller should await the question).
 * - Wake word + content -> activated, classified command/question.
 */
export function parseWakeUtterance(text: string): WakeParse {
  const after = extractAfterWake(text);
  if (after === null) return { activated: false, command: { kind: "none" } };
  if (!after) return { activated: true, command: { kind: "none" } };
  return { activated: true, command: classifyCommand(after) };
}

/**
 * Parse an utterance when we are ALREADY activated and awaiting the question
 * (wake word optional; strip it if the user repeated it).
 */
export function parseFollowUp(text: string): DriveCommand {
  const stripped = hasWakeWord(text) ? stripWakeWords(text) : (text || "").trim();
  return classifyCommand(stripped);
}

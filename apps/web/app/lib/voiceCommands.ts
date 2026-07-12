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

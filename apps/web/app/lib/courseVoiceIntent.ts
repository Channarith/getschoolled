// Pure, offline, dependency-free course-player voice intent parser.
//
// The Sala-only course player keeps the mic ALWAYS listening and routes every
// heard utterance through this parser locally in the browser. Only when a
// confident intent matches does the player act on it; raw transcripts never
// leave the device, so an open mic during a lesson is not an upload channel.
//
// Lives in app/lib so it is Server-Side-safe (no DOM, no browser globals) and
// so the Node test runner can import it directly from tests/unit.
//
// A mirror copy lives at apps/mobile/src/courseVoiceIntent.ts — the two must
// stay in lockstep. courseVoiceIntentCatalog() returns the shared vocabulary
// so a parity test can enforce that.

export type CourseVoiceIntent =
  | { kind: "pause" }
  | { kind: "resume" }
  | { kind: "restart" }
  | { kind: "start" }
  | { kind: "next" }
  | { kind: "previous" }
  | { kind: "repeat" }
  | { kind: "captions_on" }
  | { kind: "captions_off" }
  | { kind: "captions_toggle" }
  | { kind: "fullscreen_on" }
  | { kind: "fullscreen_off" }
  | { kind: "set_language"; language: string }
  | { kind: "set_speed"; speed: "slower" | "faster" | "normal" }
  | { kind: "mute_mic" }
  | { kind: "show_controls" }
  | { kind: "hide_controls" }
  | { kind: "help" }
  | { kind: "ask"; question: string };

export type CourseVoiceIntentKind = CourseVoiceIntent["kind"];

/** The full vocabulary this parser recognizes. The mobile mirror must match. */
export function courseVoiceIntentCatalog(): readonly CourseVoiceIntentKind[] {
  return [
    "pause", "resume", "restart", "start", "next", "previous", "repeat",
    "captions_on", "captions_off", "captions_toggle",
    "fullscreen_on", "fullscreen_off",
    "set_language", "set_speed",
    "mute_mic",
    "show_controls", "hide_controls",
    "help", "ask",
  ] as const;
}

// Keep the wake word optional — "sala" may precede any command but should also
// be stripped so a bare "sala pause" matches the "pause" intent.
const WAKE_RE = /\b(hey\s+sala(?:reen)?|salareen|sala)\b[\s,.:!?-]*/gi;

function normalize(text: string): string {
  return (text || "").toLowerCase().replace(WAKE_RE, " ").replace(/\s+/g, " ").trim();
}

// Map of language names a learner might say -> the BCP-47 base code used by
// the rest of the player. Kept short and extensible. A spoken language name
// not in this map falls through to the LLM-backed ``ask`` intent (so the
// learner can say e.g. "sala, please answer in Welsh" even if we don't know
// Welsh here).
const LANGUAGES: Record<string, string> = {
  english: "en", spanish: "es", french: "fr", german: "de", italian: "it",
  portuguese: "pt", dutch: "nl", polish: "pl", russian: "ru", ukrainian: "uk",
  turkish: "tr", arabic: "ar", hebrew: "he", hindi: "hi", bengali: "bn",
  urdu: "ur", persian: "fa", farsi: "fa", chinese: "zh", mandarin: "zh",
  cantonese: "yue", japanese: "ja", korean: "ko", vietnamese: "vi",
  thai: "th", indonesian: "id", swahili: "sw", greek: "el", czech: "cs",
  khmer: "km", cambodian: "km",
};

/** Canonicalize a BCP-47 base code (or null) from a spoken language name. */
export function languageCodeFromSpoken(name: string): string | null {
  const n = (name || "").toLowerCase().trim();
  if (!n) return null;
  if (LANGUAGES[n]) return LANGUAGES[n];
  // Already a BCP-47 base code the learner said directly ("en", "zh").
  if (/^[a-z]{2,3}$/.test(n) && Object.values(LANGUAGES).includes(n)) return n;
  return null;
}

/** True when the utterance is clearly meant as a question for Sala. */
function looksLikeAsk(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  if (t.endsWith("?")) return true;
  if (/^(ask|question)\b/.test(t)) return true;
  return /^(what|why|how|when|where|who|whose|which|can|could|would|will|do|does|did|is|are|should|explain|define|describe|tell me|help me)\b/.test(t);
}

/**
 * Parse an utterance into a course-player intent. Returns null when nothing
 * matches confidently; the caller counts those "misses" to decide when to
 * reveal the classic controls as a safety net.
 */
export function parseCourseVoiceIntent(utterance: string): CourseVoiceIntent | null {
  const text = normalize(utterance);
  if (!text) return null;

  // Order matters: more specific patterns (captions on, show controls) must
  // run BEFORE their broader siblings (captions, show).

  // Mute mic — the user wants to stop Sala's listening. Must be unambiguous
  // because unmute is not voice-controllable (the user has to tap to unmute).
  if (/^(stop\s+listening|mute\s+(?:the\s+)?(?:mic|microphone|yourself)|be\s+quiet(?:\s+mic)?|silence\s+(?:yourself|mic|microphone))\b/.test(text)) {
    return { kind: "mute_mic" };
  }

  // Captions / closed captions / subtitles — explicit on/off wins over toggle.
  if (/\b(?:(?:turn\s+)?(?:on|enable|show|display)\s+(?:closed\s+)?(?:captions?|subtitles?|cc)|(?:closed\s+)?(?:captions?|subtitles?|cc)\s+on)\b/.test(text)) {
    return { kind: "captions_on" };
  }
  if (/\b(?:(?:turn\s+)?(?:off|disable|hide|remove)\s+(?:closed\s+)?(?:captions?|subtitles?|cc)|(?:closed\s+)?(?:captions?|subtitles?|cc)\s+off)\b/.test(text)) {
    return { kind: "captions_off" };
  }
  if (/^(?:(?:closed\s+)?captions|subtitles|cc)$/.test(text)) {
    return { kind: "captions_toggle" };
  }

  // Fullscreen — explicit exit wins over enter.
  if (/\b(exit|leave|close|quit)\s+(?:full\s*screen|fullscreen)\b|^(?:exit|normal\s+size|smaller|minimize)$/.test(text)) {
    return { kind: "fullscreen_off" };
  }
  if (/\b(?:go\s+)?(?:full\s*screen|fullscreen)|\bmake\s+it\s+(?:bigger|full)\b|\bbigger\s+screen\b/.test(text)) {
    return { kind: "fullscreen_on" };
  }

  // Show / hide classic controls — the recovery path for voice failures.
  if (/\b(?:show|display|bring\s+(?:up|back))\s+(?:the\s+)?(?:controls?|buttons?|options?|menu)\b/.test(text)) {
    return { kind: "show_controls" };
  }
  if (/\b(?:hide|close)\s+(?:the\s+)?(?:controls?|buttons?|options?|menu)\b/.test(text)) {
    return { kind: "hide_controls" };
  }

  // Speed.
  if (/\b(slow(?:\s+down)?|slower|less\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "slower" };
  if (/\b(speed\s+up|faster|more\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "faster" };
  if (/\b(normal\s+speed|regular\s+speed|default\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "normal" };

  // Set language. "speak Spanish", "say it in Spanish", "change language to Spanish",
  // "switch to Spanish", "in Spanish please".
  const langMatch = text.match(/\b(?:speak(?:\s+in)?|say(?:\s+it)?\s+in|change\s+language\s+to|switch\s+(?:language\s+)?to|language\s+to|in)\s+([a-z\-]{2,20})\b/);
  if (langMatch) {
    const code = languageCodeFromSpoken(langMatch[1]);
    if (code) return { kind: "set_language", language: code };
  }

  // Restart (course from the beginning) — must beat "start".
  if (/\b(restart|start\s+over|from\s+the\s+beginning|back\s+to\s+(?:the\s+)?beginning)\b/.test(text)) {
    return { kind: "restart" };
  }

  // Pause / resume / start.
  if (/^(pause|stop|hold\s+on|wait|freeze)$|\b(pause|stop\s+(?:the\s+)?(?:course|lesson|class|video))\b/.test(text)) {
    return { kind: "pause" };
  }
  if (/^(resume|continue|unpause|play|keep\s+going|carry\s+on)$|\b(resume|unpause|keep\s+going|carry\s+on)\b/.test(text)) {
    return { kind: "resume" };
  }
  if (/^(start|begin)$|\b(start|begin)\s+(?:the\s+)?(?:course|lesson|class)\b/.test(text)) {
    return { kind: "start" };
  }

  // Navigation.
  if (/^(next|forward|skip|move\s+on)$|\bnext\s+(?:slide|chapter|section|step)\b|\bskip\s+ahead\b/.test(text)) {
    return { kind: "next" };
  }
  if (/^(back|previous|rewind)$|\b(previous|go\s+back|back\s+up|last\s+(?:slide|one))\b/.test(text)) {
    return { kind: "previous" };
  }
  if (/^(repeat|again)$|\b(repeat|say\s+that\s+again|come\s+again|one\s+more\s+time|do\s+it\s+again)\b/.test(text)) {
    return { kind: "repeat" };
  }

  // Help.
  if (/^(help|commands?)$|\b(what\s+can\s+i\s+say|what\s+commands|how\s+do\s+i\s+use\s+this)\b/.test(text)) {
    return { kind: "help" };
  }

  // Explicit "ask <...>" or "question <...>" strips the leader and treats the
  // remainder as a question for Sala.
  const askMatch = text.match(/^(?:ask\s+(?:sala\s+)?|question[:,-]?\s*)(.+)$/);
  if (askMatch && askMatch[1]) {
    return { kind: "ask", question: askMatch[1].trim() };
  }

  // Fallthrough: looks like a free-form question → pass to Sala.
  if (looksLikeAsk(text)) {
    return { kind: "ask", question: text };
  }

  return null;
}

/** Human-readable description used by the help overlay. */
export function describeCourseIntent(intent: CourseVoiceIntent): string {
  switch (intent.kind) {
    case "pause": return "pausing the course";
    case "resume": return "resuming the course";
    case "restart": return "restarting the course from the beginning";
    case "start": return "starting the course";
    case "next": return "going to the next slide";
    case "previous": return "going back one slide";
    case "repeat": return "repeating the last narration";
    case "captions_on": return "turning closed captions on";
    case "captions_off": return "turning closed captions off";
    case "captions_toggle": return "toggling closed captions";
    case "fullscreen_on": return "entering fullscreen";
    case "fullscreen_off": return "leaving fullscreen";
    case "set_language": return `switching narration to ${intent.language}`;
    case "set_speed": return `playing ${intent.speed}`;
    case "mute_mic": return "muting the microphone (tap the mic to unmute)";
    case "show_controls": return "showing the classic controls";
    case "hide_controls": return "hiding the controls again";
    case "help": return "showing voice-command help";
    case "ask": return `asking Sala "${intent.question}"`;
  }
}

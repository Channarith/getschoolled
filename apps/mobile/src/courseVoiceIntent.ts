// Mobile mirror of apps/web/app/lib/courseVoiceIntent.ts.
//
// The two files MUST stay in lockstep. The courseVoiceIntentCatalog() helper
// returns the shared vocabulary; a parity test (apps/mobile/src/__tests__/
// courseVoiceIntent.test.ts) and apps/web/tests/unit/courseVoiceIntent.test.mjs
// both import it to prove they agree on the kinds they recognize.
//
// Monorepo note: the file is duplicated instead of symlinked / cross-imported
// so Metro (mobile) and Next.js (web) can each resolve it with their own
// bundler without a shared package build step.

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

const WAKE_RE = /\b(hey\s+sala(?:reen)?|salareen|sala)\b[\s,.:!?-]*/gi;

function normalize(text: string): string {
  return (text || "").toLowerCase().replace(WAKE_RE, " ").replace(/\s+/g, " ").trim();
}

const LANGUAGES: Record<string, string> = {
  english: "en", spanish: "es", french: "fr", german: "de", italian: "it",
  portuguese: "pt", dutch: "nl", polish: "pl", russian: "ru", ukrainian: "uk",
  turkish: "tr", arabic: "ar", hebrew: "he", hindi: "hi", bengali: "bn",
  urdu: "ur", persian: "fa", farsi: "fa", chinese: "zh", mandarin: "zh",
  cantonese: "yue", japanese: "ja", korean: "ko", vietnamese: "vi",
  thai: "th", indonesian: "id", swahili: "sw", greek: "el", czech: "cs",
  khmer: "km", cambodian: "km",
};

export function languageCodeFromSpoken(name: string): string | null {
  const n = (name || "").toLowerCase().trim();
  if (!n) return null;
  if (LANGUAGES[n]) return LANGUAGES[n];
  if (/^[a-z]{2,3}$/.test(n) && Object.values(LANGUAGES).includes(n)) return n;
  return null;
}

function looksLikeAsk(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  if (t.endsWith("?")) return true;
  if (/^(ask|question)\b/.test(t)) return true;
  return /^(what|why|how|when|where|who|whose|which|can|could|would|will|do|does|did|is|are|should|explain|define|describe|tell me|help me)\b/.test(t);
}

export function parseCourseVoiceIntent(utterance: string): CourseVoiceIntent | null {
  const text = normalize(utterance);
  if (!text) return null;

  if (/^(stop\s+listening|mute\s+(?:the\s+)?(?:mic|microphone|yourself)|be\s+quiet(?:\s+mic)?|silence\s+(?:yourself|mic|microphone))\b/.test(text)) {
    return { kind: "mute_mic" };
  }

  if (/\b(?:(?:turn\s+)?(?:on|enable|show|display)\s+(?:closed\s+)?(?:captions?|subtitles?|cc)|(?:closed\s+)?(?:captions?|subtitles?|cc)\s+on)\b/.test(text)) {
    return { kind: "captions_on" };
  }
  if (/\b(?:(?:turn\s+)?(?:off|disable|hide|remove)\s+(?:closed\s+)?(?:captions?|subtitles?|cc)|(?:closed\s+)?(?:captions?|subtitles?|cc)\s+off)\b/.test(text)) {
    return { kind: "captions_off" };
  }
  if (/^(?:(?:closed\s+)?captions|subtitles|cc)$/.test(text)) {
    return { kind: "captions_toggle" };
  }

  if (/\b(exit|leave|close|quit)\s+(?:full\s*screen|fullscreen)\b|^(?:exit|normal\s+size|smaller|minimize)$/.test(text)) {
    return { kind: "fullscreen_off" };
  }
  if (/\b(?:go\s+)?(?:full\s*screen|fullscreen)|\bmake\s+it\s+(?:bigger|full)\b|\bbigger\s+screen\b/.test(text)) {
    return { kind: "fullscreen_on" };
  }

  if (/\b(?:show|display|bring\s+(?:up|back))\s+(?:the\s+)?(?:controls?|buttons?|options?|menu)\b/.test(text)) {
    return { kind: "show_controls" };
  }
  if (/\b(?:hide|close)\s+(?:the\s+)?(?:controls?|buttons?|options?|menu)\b/.test(text)) {
    return { kind: "hide_controls" };
  }

  if (/\b(slow(?:\s+down)?|slower|less\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "slower" };
  if (/\b(speed\s+up|faster|more\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "faster" };
  if (/\b(normal\s+speed|regular\s+speed|default\s+speed)\b/.test(text)) return { kind: "set_speed", speed: "normal" };

  const langMatch = text.match(/\b(?:speak(?:\s+in)?|say(?:\s+it)?\s+in|change\s+language\s+to|switch\s+(?:language\s+)?to|language\s+to|in)\s+([a-z\-]{2,20})\b/);
  if (langMatch) {
    const code = languageCodeFromSpoken(langMatch[1]);
    if (code) return { kind: "set_language", language: code };
  }

  if (/\b(restart|start\s+over|from\s+the\s+beginning|back\s+to\s+(?:the\s+)?beginning)\b/.test(text)) {
    return { kind: "restart" };
  }

  if (/^(pause|stop|hold\s+on|wait|freeze)$|\b(pause|stop\s+(?:the\s+)?(?:course|lesson|class|video))\b/.test(text)) {
    return { kind: "pause" };
  }
  if (/^(resume|continue|unpause|play|keep\s+going|carry\s+on)$|\b(resume|unpause|keep\s+going|carry\s+on)\b/.test(text)) {
    return { kind: "resume" };
  }
  if (/^(start|begin)$|\b(start|begin)\s+(?:the\s+)?(?:course|lesson|class)\b/.test(text)) {
    return { kind: "start" };
  }

  if (/^(next|forward|skip|move\s+on)$|\bnext\s+(?:slide|chapter|section|step)\b|\bskip\s+ahead\b/.test(text)) {
    return { kind: "next" };
  }
  if (/^(back|previous|rewind)$|\b(previous|go\s+back|back\s+up|last\s+(?:slide|one))\b/.test(text)) {
    return { kind: "previous" };
  }
  if (/^(repeat|again)$|\b(repeat|say\s+that\s+again|come\s+again|one\s+more\s+time|do\s+it\s+again)\b/.test(text)) {
    return { kind: "repeat" };
  }

  if (/^(help|commands?)$|\b(what\s+can\s+i\s+say|what\s+commands|how\s+do\s+i\s+use\s+this)\b/.test(text)) {
    return { kind: "help" };
  }

  const askMatch = text.match(/^(?:ask\s+(?:sala\s+)?|question[:,-]?\s*)(.+)$/);
  if (askMatch && askMatch[1]) {
    return { kind: "ask", question: askMatch[1].trim() };
  }

  if (looksLikeAsk(text)) {
    return { kind: "ask", question: text };
  }

  return null;
}

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

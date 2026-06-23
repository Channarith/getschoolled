// Natural-sounding Web Speech API narration for Drive Mode.
//
// The browser's default voice is usually the robotic one and ignores the
// content language. These helpers (1) map the UI locale to a BCP-47 tag so the
// engine uses the right-accent voice, and (2) pick the best *natural / neural*
// voice the device exposes (Google/Microsoft "Natural"/"Online", Apple
// "Siri"/"Enhanced", etc.) instead of the legacy formant voice. For fully
// human-grade audio, route narration through a neural TTS backend (XTTS / cloud
// TTS via the speech service) — see speakNaturally's `audioUrl` hook.

const LOCALE_TO_BCP47: Record<string, string> = {
  en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT",
  pt: "pt-BR", ru: "ru-RU", ar: "ar-SA", hi: "hi-IN", zh: "zh-CN",
  ja: "ja-JP", ko: "ko-KR", vi: "vi-VN", km: "km-KH",
};

export function localeToBcp47(locale: string): string {
  return LOCALE_TO_BCP47[locale] || locale || "en-US";
}

type VoiceLike = {
  name?: string;
  lang?: string;
  localService?: boolean;
  default?: boolean;
};

// Legacy "formant" voices that sound robotic - demote hard so we never pick them
// when anything better exists (mostly macOS novelty/compact voices + a few others).
const ROBOTIC_VOICES =
  /\b(albert|fred|junior|kathy|ralph|zarvox|bahh|bells|boing|bubbles|cellos|deranged|hysterical|organ|pipe|trinoids|whisper|wobble|jester|superstar|bad news|good news|grandma|grandpa|rocko|sandy|shelley|eddy|flo|reed|rishi|sinji|grandpa|novelty)\b/;
// Known high-quality, human-grade voice families.
const PREMIUM_VOICES = /\b(natural|neural|wavenet|journey|studio|premium|enhanced)\b/;
const GOOD_VOICES = /(google|online|siri|samantha|aria|jenny|guy|libby|sonia)/;

// Higher = more natural. Pure function so it can be unit-tested.
export function scoreVoice(v: VoiceLike, lang: string): number {
  const name = (v.name || "").toLowerCase();
  const vlang = (v.lang || "").toLowerCase();
  let s = 0;
  if (vlang === lang.toLowerCase()) s += 3;               // exact locale (accent) match
  else if (vlang.split("-")[0] === lang.split("-")[0].toLowerCase()) s += 1;
  if (PREMIUM_VOICES.test(name)) s += 8;                  // best modern (neural) voices
  else if (GOOD_VOICES.test(name)) s += 5;                // good cloud/system voices
  else if (/(microsoft|nuance)/.test(name)) s += 2;
  if (ROBOTIC_VOICES.test(name)) s -= 10;                 // never pick formant voices
  if (v.localService === false) s += 2;                   // cloud voices are higher quality
  if (v.default) s += 1;
  return s;
}

// Pick the best voice matching the target language's primary subtag.
export function pickVoice<T extends VoiceLike>(voices: T[], lang: string): T | undefined {
  if (!voices || !voices.length) return undefined;
  const primary = lang.split("-")[0].toLowerCase();
  const matches = voices.filter(
    (v) => (v.lang || "").toLowerCase().split("-")[0] === primary,
  );
  const pool = matches.length ? matches : voices;
  return [...pool].sort((a, b) => scoreVoice(b, lang) - scoreVoice(a, lang))[0];
}

// Voice lists load asynchronously; resolve once they're available (or after a
// short timeout so we never hang).
export function ensureVoices(timeoutMs = 1500): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      resolve([]);
      return;
    }
    const synth = window.speechSynthesis;
    const have = synth.getVoices();
    if (have.length) {
      resolve(have);
      return;
    }
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      resolve(synth.getVoices());
    };
    synth.addEventListener?.("voiceschanged", finish, { once: true });
    setTimeout(finish, timeoutMs);
  });
}

export type SpeakOptions = {
  locale: string;
  rate?: number;
  pitch?: number;
  onend?: () => void;
};

// Split narration into natural speech chunks (sentence/clause boundaries). The
// engine inserts a brief, lifelike pause between queued utterances, so chunking
// fixes the flat, run-on, "robotic" delivery you get from one giant utterance.
export function splitForSpeech(text: string): string[] {
  return (text || "")
    .replace(/\s+/g, " ")
    .trim()
    // break after sentence enders, and also after colons/semicolons for pacing.
    .split(/(?<=[.!?:;])\s+/)
    .flatMap((s) => (s.length > 180 ? s.split(/(?<=,)\s+/) : [s])) // long clauses too
    .map((s) => s.trim())
    .filter(Boolean);
}

// Speak `text` with the best natural voice for the locale + lifelike prosody.
// Chunks the text and queues the chunks so the engine paces sentences naturally;
// a slightly slower rate reads warmer and clearer than the default.
export function speakNaturally(text: string, opts: SpeakOptions): void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    opts.onend?.();
    return;
  }
  const synth = window.speechSynthesis;
  const lang = localeToBcp47(opts.locale);
  const voice = pickVoice(synth.getVoices(), lang);
  const chunks = splitForSpeech(text);

  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    opts.onend?.();
  };
  if (!chunks.length) {
    done();
    return;
  }
  chunks.forEach((chunk, i) => {
    const u = new SpeechSynthesisUtterance(chunk);
    u.lang = lang;
    if (voice) u.voice = voice;
    // ~0.95 is clearer/warmer than the rushed default 1.0; pitch neutral.
    u.rate = opts.rate ?? 0.95;
    u.pitch = opts.pitch ?? 1.0;
    if (i === chunks.length - 1) u.onend = done; // resolve after the last chunk
    u.onerror = done;                            // and on cancel/error (once)
    synth.speak(u);
  });
}

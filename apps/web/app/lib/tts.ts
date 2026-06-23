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

// Higher = more natural. Pure function so it can be unit-tested.
export function scoreVoice(v: VoiceLike, lang: string): number {
  const name = (v.name || "").toLowerCase();
  const vlang = (v.lang || "").toLowerCase();
  let s = 0;
  if (vlang === lang.toLowerCase()) s += 3; // exact locale (accent) match
  if (/\b(natural|neural|wavenet)\b/.test(name)) s += 6; // best modern voices
  else if (/(online|google|premium|enhanced|siri)/.test(name)) s += 4;
  else if (/(microsoft|nuance)/.test(name)) s += 1;
  if (v.localService === false) s += 1; // cloud voices are usually higher quality
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

// Speak `text` with the best natural voice for the locale + lifelike prosody.
export function speakNaturally(text: string, opts: SpeakOptions): void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    opts.onend?.();
    return;
  }
  const synth = window.speechSynthesis;
  const lang = localeToBcp47(opts.locale);
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  const voice = pickVoice(synth.getVoices(), lang);
  if (voice) u.voice = voice;
  u.rate = opts.rate ?? 1;
  // A touch below neutral reads warmer/less robotic; engines clamp out of range.
  u.pitch = opts.pitch ?? 0.95;
  u.onend = () => opts.onend?.();
  u.onerror = () => opts.onend?.();
  synth.speak(u);
}

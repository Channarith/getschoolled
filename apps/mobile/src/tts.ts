// Natural-sounding narration for mobile Drive Mode (expo-speech).
//
// Without options expo-speech uses the OS default voice and ignores the content
// language, which sounds robotic and mispronounces non-English text. These
// helpers map the UI locale to a BCP-47 tag and pick the device's best
// (Enhanced) voice for that language, with warmer prosody. For fully human-grade
// audio, route narration through a neural TTS backend (XTTS / cloud TTS).
import * as Speech from "expo-speech";

import {
  prosodyForStyle, type NarrationVoiceStyle, voiceNameStyleBonus,
} from "./voiceProfiles";

const LOCALE_TO_BCP47: Record<string, string> = {
  en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT",
  pt: "pt-BR", ru: "ru-RU", ar: "ar-SA", hi: "hi-IN", zh: "zh-CN",
  ja: "ja-JP", ko: "ko-KR", vi: "vi-VN", km: "km-KH",
};

export function localeToBcp47(locale: string): string {
  return LOCALE_TO_BCP47[locale] || locale || "en-US";
}

let voicesCache: Speech.Voice[] | null = null;

// Load the device voice list once (used to prefer Enhanced/neural voices).
export async function warmVoices(): Promise<void> {
  if (voicesCache) return;
  try {
    voicesCache = await Speech.getAvailableVoicesAsync();
  } catch {
    voicesCache = [];
  }
}

function pickVoiceId(lang: string, style: NarrationVoiceStyle = "standard"): string | undefined {
  if (!voicesCache || !voicesCache.length) return undefined;
  const primary = lang.split("-")[0].toLowerCase();
  const matches = voicesCache.filter(
    (v) => (v.language || "").toLowerCase().split("-")[0] === primary,
  );
  if (!matches.length) return undefined;
  const ranked = [...matches].sort((a, b) => {
    const score = (v: Speech.Voice) =>
      (v.quality === Speech.VoiceQuality.Enhanced ? 2 : 0) +
      ((v.language || "").toLowerCase() === lang.toLowerCase() ? 1 : 0) +
      voiceNameStyleBonus(style, v.name || "");
    return score(b) - score(a);
  });
  return ranked[0].identifier;
}

export type SpeakOptions = {
  locale: string;
  voiceStyle?: NarrationVoiceStyle;
  rate?: number;
  pitch?: number;
  onDone?: () => void;
  onStopped?: () => void;
  onError?: () => void;
};

// Speak with the best natural voice for the locale + lifelike prosody.
export function speakNatural(text: string, opts: SpeakOptions): void {
  const style = opts.voiceStyle ?? "standard";
  const prosody = prosodyForStyle(style);
  const lang = localeToBcp47(opts.locale);
  Speech.speak(text, {
    language: lang,
    voice: pickVoiceId(lang, style),
    pitch: opts.pitch ?? prosody.pitch,
    rate: opts.rate ?? prosody.rate,
    onDone: opts.onDone,
    onStopped: opts.onStopped,
    onError: opts.onError,
  });
}

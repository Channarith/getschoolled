// Natural-sounding narration for mobile Drive Mode (expo-speech).
//
// Without options expo-speech uses the OS default voice and ignores the content
// language, which sounds robotic and mispronounces non-English text. These
// helpers map the UI locale to a BCP-47 tag and pick the device's best
// (Enhanced) voice for that language, with warmer prosody. For fully human-grade
// audio, route narration through a neural TTS backend (XTTS / cloud TTS).
import { Audio, InterruptionModeAndroid, InterruptionModeIOS } from "expo-av";
import * as Speech from "expo-speech";

import {
  prosodyForStyle, type NarrationVoiceStyle, voiceNameStyleBonus,
} from "./voiceProfiles";

// BCP-47 tag for every platform-supported language, so TTS uses a
// right-accent voice for the spoken (training) locale.
const LOCALE_TO_BCP47: Record<string, string> = {
  en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT",
  pt: "pt-BR", nl: "nl-NL", pl: "pl-PL", ru: "ru-RU", uk: "uk-UA",
  tr: "tr-TR", ar: "ar-SA", he: "he-IL", hi: "hi-IN", bn: "bn-BD",
  ur: "ur-PK", fa: "fa-IR", zh: "zh-CN", ja: "ja-JP", ko: "ko-KR",
  vi: "vi-VN", th: "th-TH", id: "id-ID", sw: "sw-KE", el: "el-GR",
  cs: "cs-CZ", km: "km-KH",
};

export function localeToBcp47(locale: string): string {
  return LOCALE_TO_BCP47[locale] || locale || "en-US";
}

// expo-speech (iOS AVSpeechSynthesizer) shares the app-wide AVAudioSession.
// Without an explicit playback category iOS silences narration when the
// hardware mute switch is on, and after LiveKit / the intro jingle grab and
// release the session it can be left ducked or routed so TTS is inaudible.
// Re-assert a playback session before speaking so lesson audio always plays.
let audioSessionReady = false;

export async function ensureSpeechAudioSession(): Promise<void> {
  try {
    await Audio.setAudioModeAsync({
      playsInSilentModeIOS: true,
      staysActiveInBackground: true,
      interruptionModeIOS: InterruptionModeIOS.DuckOthers,
      interruptionModeAndroid: InterruptionModeAndroid.DuckOthers,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
    });
    audioSessionReady = true;
  } catch {
    // Non-fatal: fall back to expo-speech's default audio session.
    audioSessionReady = false;
  }
}

let voicesCache: Speech.Voice[] | null = null;

// Load the device voice list once (used to prefer Enhanced/neural voices).
export async function warmVoices(): Promise<void> {
  if (!audioSessionReady) await ensureSpeechAudioSession();
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
  void (async () => {
    // Configure the playback session first so iOS actually routes TTS to the
    // speaker (mute switch on, or after LiveKit/intro released the session).
    await ensureSpeechAudioSession();
    Speech.speak(text, {
      language: lang,
      voice: pickVoiceId(lang, style),
      pitch: opts.pitch ?? prosody.pitch,
      rate: opts.rate ?? prosody.rate,
      onDone: opts.onDone,
      onStopped: opts.onStopped,
      onError: opts.onError,
    });
  })();
}

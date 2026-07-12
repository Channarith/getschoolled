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

// --------------------------------------------------------------------------- //
// Server neural TTS (ElevenLabs -> edge-tts) with graceful expo-speech fallback.
// When the speech gateway has a neural engine we stream MP3 audio (far more
// natural / cultural than the on-device voice); otherwise we use expo-speech.
let _speechBaseUrl = "";
let _serverTtsReady: boolean | null = null;
let _statusProbe: Promise<boolean> | null = null;
let _serverSound: Audio.Sound | null = null;
let _serverVoiceId = "";   // chosen voice_catalog id (accent/language)

export function setServerVoice(voiceId: string): void {
  _serverVoiceId = voiceId || "";
}

export function getServerVoice(): string {
  return _serverVoiceId;
}
// GET /tts is used so expo-av can load a URI directly; keep segments within a
// safe URL length, else fall back to the device voice for that segment.
const MAX_SERVER_TTS_CHARS = 3000;

export function configureServerTts(baseUrl: string): void {
  _speechBaseUrl = (baseUrl || "").replace(/\/$/, "");
}

async function serverTtsAvailable(): Promise<boolean> {
  if (!_speechBaseUrl) return false;
  if (_serverTtsReady !== null) return _serverTtsReady;
  if (!_statusProbe) {
    _statusProbe = fetch(`${_speechBaseUrl}/tts/status`)
      .then((r) => (r.ok ? r.json() : { available: false }))
      .then((j) => Boolean(j?.available))
      .catch(() => false)
      .then((ok) => { _serverTtsReady = ok; return ok; });
  }
  return _statusProbe;
}

async function stopServerSound(): Promise<void> {
  const s = _serverSound;
  _serverSound = null;
  if (s) {
    try { await s.stopAsync(); } catch { /* */ }
    try { await s.unloadAsync(); } catch { /* */ }
  }
}

// Stop ALL narration (device voice AND server audio).
export function stopSpeech(): void {
  try { Speech.stop(); } catch { /* */ }
  void stopServerSound();
}

async function playServerAudio(text: string, opts: SpeakOptions): Promise<boolean> {
  if (encodeURIComponent(text).length > MAX_SERVER_TTS_CHARS) return false;
  try {
    await ensureSpeechAudioSession();
    const lang = (opts.locale || "en").split("-")[0];
    const style = opts.voiceStyle ?? "standard";
    const uri = `${_speechBaseUrl}/tts?text=${encodeURIComponent(text)}`
      + `&language=${encodeURIComponent(lang)}&voice_style=${encodeURIComponent(style)}`
      + (_serverVoiceId ? `&voice=${encodeURIComponent(_serverVoiceId)}` : "");
    const { sound, status } = await Audio.Sound.createAsync({ uri }, { shouldPlay: true });
    if (!status.isLoaded) {
      try { await sound.unloadAsync(); } catch { /* */ }
      return false;
    }
    await stopServerSound();
    _serverSound = sound;
    let ended = false;
    const finish = (cb?: () => void) => {
      if (ended) return;
      ended = true;
      void stopServerSound();
      cb?.();
    };
    sound.setOnPlaybackStatusUpdate((st) => {
      if (!st.isLoaded) {
        if ((st as { error?: string }).error) finish(opts.onError);
        return;
      }
      if (st.didJustFinish) finish(opts.onDone);
    });
    return true;
  } catch {
    await stopServerSound();
    return false;
  }
}

// Speak with the most natural voice available: server neural audio when the
// gateway offers it, else the best on-device voice + lifelike prosody.
export function speakNatural(text: string, opts: SpeakOptions): void {
  const style = opts.voiceStyle ?? "standard";
  const prosody = prosodyForStyle(style);
  const lang = localeToBcp47(opts.locale);
  const speakDevice = () => {
    Speech.speak(text, {
      language: lang,
      voice: pickVoiceId(lang, style),
      pitch: opts.pitch ?? prosody.pitch,
      rate: opts.rate ?? prosody.rate,
      onDone: opts.onDone,
      onStopped: opts.onStopped,
      onError: opts.onError,
    });
  };
  void (async () => {
    // Configure the playback session first so iOS actually routes TTS to the
    // speaker (mute switch on, or after LiveKit/intro released the session).
    await ensureSpeechAudioSession();
    if (await serverTtsAvailable()) {
      if (await playServerAudio(text, opts)) return;   // neural audio playing
    }
    speakDevice();                                     // fallback
  })();
}

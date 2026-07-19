// Natural-sounding narration for mobile Drive Mode (expo-speech).
//
// Without options expo-speech uses the OS default voice and ignores the content
// language, which sounds robotic and mispronounces non-English text. These
// helpers map the UI locale to a BCP-47 tag and pick the device's best
// (Enhanced) voice for that language, with warmer prosody. For fully human-grade
// audio, route narration through a neural TTS backend (XTTS / cloud TTS).
import { Audio, InterruptionModeAndroid, InterruptionModeIOS } from "expo-av";
import * as Speech from "expo-speech";

import { ensureLiveRoomNarrationRoute, liveKitAudioActive } from "./components/liveKitAudio";
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

// Split narration into sentence/clause chunks. The on-device engine (Android
// TextToSpeech in particular) truncates long input — Android's
// getMaxSpeechInputLength caps a single utterance (~4000 chars) and long
// utterances can be cut off mid-sentence. Queuing short chunks (expo-speech
// plays queued calls sequentially) narrates the whole lesson without cutoff.
export function splitForSpeech(text: string): string[] {
  return (text || "")
    .replace(/\s+/g, " ")
    .trim()
    .split(/(?<=[.!?:;])\s+/)
    .flatMap((s) => (s.length > 180 ? s.split(/(?<=,)\s+/) : [s]))
    .map((s) => s.trim())
    .filter(Boolean);
}

// expo-speech (iOS AVSpeechSynthesizer) shares the app-wide AVAudioSession.
// Without an explicit playback category iOS silences narration when the
// hardware mute switch is on, and after LiveKit / the intro jingle grab and
// release the session it can be left ducked or routed so TTS is inaudible.
// Re-assert a playback session before speaking so lesson audio always plays.
// MixWithOthers (not DuckOthers) so live-room TTS can share the session with
// LiveKit WebRTC instead of fighting it into silence.
let audioSessionReady = false;

export async function ensureSpeechAudioSession(): Promise<void> {
  try {
    await Audio.setAudioModeAsync({
      playsInSilentModeIOS: true,
      staysActiveInBackground: true,
      interruptionModeIOS: InterruptionModeIOS.MixWithOthers,
      interruptionModeAndroid: InterruptionModeAndroid.DuckOthers,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
    });
    // LiveKit owns AVAudioSession in a live room — re-assert speaker AFTER
    // expo-av so teacher TTS isn't left on the earpiece / silent category.
    if (liveKitAudioActive()) {
      await ensureLiveRoomNarrationRoute();
    }
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

// Heuristic gendered voice-name tokens so a male/female choice biases the
// on-device voice too (the OS voice list rarely exposes a structured gender).
const FEMALE_VOICES = /\b(female|woman|aria|jenny|sonia|natasha|clara|leah|samantha|susan|zira|hazel|catherine|fiona|moira|tessa|karen|serena|allison|ava|joanna|emma|amy|libby|michelle|nova|elvira|dalia|elena|paloma|denise|sylvie|katja|elsa|francisca|raquel|nanami|sunhi|swara|xiaoxiao|hsiaochen|hiumaan|neerja|emily)\b/;
const MALE_VOICES = /\b(male|man|guy|ryan|william|davis|george|mark|daniel|alex|fred|tom|oliver|james|brian|arthur|eric|conrad|alvaro|jorge|prabhat|yunxi|aaron|arthur)\b/;

// Approximate an instructor personality with prosody multipliers so picking
// child/strict/energetic/… audibly changes the on-device voice (mirrors web).
export function personaProsody(persona?: string): { rate: number; pitch: number } {
  const p = (persona || "").toLowerCase();
  if (!p) return { rate: 1, pitch: 1 };
  if (/child|kid|cartoon|young/.test(p)) return { rate: 1.05, pitch: 1.4 };
  if (/strict|stern|drill|serious|firm/.test(p)) return { rate: 0.94, pitch: 0.82 };
  if (/energet|hype|excite|coach|lively|upbeat/.test(p)) return { rate: 1.12, pitch: 1.12 };
  if (/calm|gentle|kind|warm|sooth|friendly|patient/.test(p)) return { rate: 0.96, pitch: 1.03 };
  if (/story|narrat|deep|documentary/.test(p)) return { rate: 0.9, pitch: 0.92 };
  if (/robot|announcer|news/.test(p)) return { rate: 1.0, pitch: 0.9 };
  return { rate: 1, pitch: 1 };
}

function pickVoiceId(
  lang: string, style: NarrationVoiceStyle = "standard", gender = "",
): string | undefined {
  if (!voicesCache || !voicesCache.length) return undefined;
  const primary = lang.split("-")[0].toLowerCase();
  const matches = voicesCache.filter(
    (v) => (v.language || "").toLowerCase().split("-")[0] === primary,
  );
  if (!matches.length) return undefined;
  const g = gender.toLowerCase();
  const ranked = [...matches].sort((a, b) => {
    const score = (v: Speech.Voice) => {
      const name = (v.name || "").toLowerCase();
      let s = (v.quality === Speech.VoiceQuality.Enhanced ? 2 : 0)
        + ((v.language || "").toLowerCase() === lang.toLowerCase() ? 1 : 0)
        + voiceNameStyleBonus(style, v.name || "");
      if (g.startsWith("f")) { if (FEMALE_VOICES.test(name)) s += 4; else if (MALE_VOICES.test(name)) s -= 3; }
      else if (g.startsWith("m")) { if (MALE_VOICES.test(name)) s += 4; else if (FEMALE_VOICES.test(name)) s -= 3; }
      return s;
    };
    return score(b) - score(a);
  });
  return ranked[0].identifier;
}

export type SpeakOptions = {
  locale: string;
  voiceStyle?: NarrationVoiceStyle;
  rate?: number;
  pitch?: number;
  // The chosen accent as a BCP-47 tag (e.g. "en-GB") so the accent picker
  // changes the on-device voice too, not only the neural server voice.
  voiceLocale?: string;
  // The chosen voice's gender ("female"/"male") — biases on-device voice pick.
  voiceGender?: string;
  // The chosen instructor personality id — approximated with prosody on-device.
  persona?: string;
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
// Bumped by stopSpeech() so in-flight async speakNatural() cannot restart audio
// after Leave / Close / mute.
let _speechEpoch = 0;
let _serverVoiceId = "";       // chosen voice_catalog id (accent/language)
let _serverInstructor = "";    // chosen instructor personality id

export function setServerVoice(voiceId: string): void {
  _serverVoiceId = voiceId || "";
}

export function getServerVoice(): string {
  return _serverVoiceId;
}

export function setServerInstructor(instructorId: string): void {
  _serverInstructor = instructorId || "";
}

export function getServerInstructor(): string {
  return _serverInstructor;
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

// Stop ALL narration (device voice AND server audio). Bumping the epoch also
// invalidates any in-flight speakNatural so it cannot start after Leave/Close.
export function stopSpeech(): void {
  _speechEpoch += 1;
  try { Speech.stop(); } catch { /* */ }
  void stopServerSound();
}

async function playServerAudio(text: string, opts: SpeakOptions, myEpoch: number): Promise<boolean> {
  if (encodeURIComponent(text).length > MAX_SERVER_TTS_CHARS) return false;
  try {
    await ensureSpeechAudioSession();
    if (_speechEpoch !== myEpoch) return true;
    const lang = (opts.locale || "en").split("-")[0];
    const style = opts.voiceStyle ?? "standard";
    const uri = `${_speechBaseUrl}/tts?text=${encodeURIComponent(text)}`
      + `&language=${encodeURIComponent(lang)}&voice_style=${encodeURIComponent(style)}`
      + (_serverVoiceId ? `&voice=${encodeURIComponent(_serverVoiceId)}` : "")
      + (_serverInstructor ? `&instructor=${encodeURIComponent(_serverInstructor)}` : "");
    const { sound, status } = await Audio.Sound.createAsync({ uri }, { shouldPlay: true });
    if (_speechEpoch !== myEpoch) {
      try { await sound.unloadAsync(); } catch { /* */ }
      return true;
    }
    if (!status.isLoaded) {
      try { await sound.unloadAsync(); } catch { /* */ }
      return false;
    }
    await stopServerSound();
    if (_speechEpoch !== myEpoch) {
      try { await sound.unloadAsync(); } catch { /* */ }
      return true;
    }
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
    if (_speechEpoch !== myEpoch) return true;
    await stopServerSound();
    return false;
  }
}

// Speak with the most natural voice available: server neural audio when the
// gateway offers it, else the best on-device voice + lifelike prosody.
export function speakNatural(text: string, opts: SpeakOptions): void {
  const myEpoch = _speechEpoch;
  const style = opts.voiceStyle ?? "standard";
  const prosody = prosodyForStyle(style);
  const persona = personaProsody(opts.persona);
  // Prefer the picked accent (voiceLocale) so the accent selector changes the
  // on-device voice too; fall back to the content locale.
  const lang = opts.voiceLocale || localeToBcp47(opts.locale);
  const speakDevice = () => {
    if (_speechEpoch !== myEpoch) return;
    const voice = pickVoiceId(lang, style, opts.voiceGender);
    // Persona shapes the delivery on top of the style's base prosody so the
    // instructor selection is audible even on the device voice.
    const rate = (opts.rate ?? prosody.rate) * persona.rate;
    const pitch = (opts.pitch ?? prosody.pitch) * persona.pitch;
    // Queue sentence-sized chunks so long narration isn't truncated by the
    // OS TTS input limit; fire onDone only after the final chunk.
    const chunks = splitForSpeech(text);
    if (!chunks.length) { opts.onDone?.(); return; }
    chunks.forEach((chunk, i) => {
      const last = i === chunks.length - 1;
      Speech.speak(chunk, {
        language: lang,
        voice,
        pitch,
        rate,
        onDone: last ? opts.onDone : undefined,
        onStopped: last ? opts.onStopped : undefined,
        onError: opts.onError,
      });
    });
  };
  void (async () => {
    // Configure the playback session first so iOS actually routes TTS to the
    // speaker (mute switch on, or after LiveKit/intro released the session).
    await ensureSpeechAudioSession();
    if (_speechEpoch !== myEpoch) return;
    if (await serverTtsAvailable()) {
      if (_speechEpoch !== myEpoch) return;
      if (await playServerAudio(text, opts, myEpoch)) return;   // neural audio playing
    }
    if (_speechEpoch !== myEpoch) return;
    speakDevice();                                     // fallback
  })();
}

// Drive Mode voice assistant — uses the device's native speech engine:
//   iOS: SFSpeechRecognizer (same stack as Siri dictation)
//   Android: SpeechRecognizer (Google on most devices)
//   Web: Web Speech API fallback
//
// Third-party apps cannot register a global "Hey Sala" wake word like Hey Siri;
// tap Ask/Mic to speak, optionally prefixed with "Hey Sala" or "Salareen".

import { Linking, Platform } from "react-native";

import { isExpoSpeechRecognitionAvailable, tryRequireModule } from "./nativeModules";

const LOCALE_TO_BCP47: Record<string, string> = {
  en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT",
  pt: "pt-BR", ru: "ru-RU", ar: "ar-SA", hi: "hi-IN", zh: "zh-CN",
  ja: "ja-JP", ko: "ko-KR", vi: "vi-VN", km: "km-KH",
};

function localeToBcp47(locale: string): string {
  return LOCALE_TO_BCP47[locale] || locale || "en-US";
}

export type VoiceEngineLabel = "Siri" | "Google" | "Alexa" | "System" | "Browser";

const WAKE_RE = /\b(hey\s+sala|sala|salareen)\b/i;

const CONTEXTUAL_PHRASES = [
  "Sala", "Salareen", "Hey Sala", "Hey Salareen",
  "pause", "resume", "continue", "next", "previous", "stop",
  "萨拉", "萨拉丁",
];

type ListenerRemover = { remove: () => void };

type SpeechRecognitionModule = {
  isRecognitionAvailable: () => boolean;
  requestPermissionsAsync: () => Promise<{ granted: boolean }>;
  getDefaultRecognitionService: () => Promise<{ packageName?: string } | null>;
  abort: () => void;
  stop: () => void;
  start: (opts: Record<string, unknown>) => void;
};

type SpeechRecognitionEvents = {
  addSpeechRecognitionListener: (
    event: string,
    listener: (event: Record<string, unknown>) => void,
  ) => ListenerRemover;
};

type WebRecognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: { [i: number]: { [j: number]: { transcript?: string } } } }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
};

let activeListeners: ListenerRemover[] = [];
let webRecognition: WebRecognition | null = null;

function getSpeechRecognition(): SpeechRecognitionEvents & {
  ExpoSpeechRecognitionModule: SpeechRecognitionModule;
} | null {
  return tryRequireModule("expo-speech-recognition");
}

function getSpeechModule(): SpeechRecognitionModule | null {
  return getSpeechRecognition()?.ExpoSpeechRecognitionModule ?? null;
}

export function getVoiceEngineLabel(): VoiceEngineLabel {
  if (Platform.OS === "ios") return "Siri";
  if (Platform.OS === "android") return "Google";
  if (Platform.OS === "web") return "Browser";
  return "System";
}

export function hasWakeWord(text: string): boolean {
  return WAKE_RE.test(text);
}

export function stripWakeWords(text: string): string {
  return text
    .replace(/\bhey\s+sala\b/ig, "")
    .replace(/\bsalareen\b/ig, "")
    .replace(/\bsala\b/ig, "")
    .trim();
}

export async function isVoiceRecognitionAvailable(): Promise<boolean> {
  if (Platform.OS === "web") {
    const root = globalThis as typeof globalThis & {
      SpeechRecognition?: new () => WebRecognition;
      webkitSpeechRecognition?: new () => WebRecognition;
    };
    return Boolean(root.SpeechRecognition || root.webkitSpeechRecognition);
  }
  const mod = getSpeechModule();
  if (!mod) return false;
  try {
    return mod.isRecognitionAvailable();
  } catch {
    return false;
  }
}

export function isNativeVoiceRecognitionLinked(): boolean {
  return isExpoSpeechRecognitionAvailable();
}

export async function ensureVoicePermissions(): Promise<boolean> {
  if (Platform.OS === "web") return true;
  const mod = getSpeechModule();
  if (!mod) return false;
  try {
    const result = await mod.requestPermissionsAsync();
    return result.granted;
  } catch {
    return false;
  }
}

export async function getVoiceEngineDetails(): Promise<{
  label: VoiceEngineLabel;
  detail?: string;
}> {
  const label = getVoiceEngineLabel();
  if (Platform.OS === "android") {
    const mod = getSpeechModule();
    if (!mod) return { label };
    try {
      const svc = await mod.getDefaultRecognitionService();
      const pkg = svc?.packageName ?? "";
      if (pkg.includes("google")) return { label: "Google", detail: pkg };
      if (pkg.includes("amazon") || pkg.includes("alexa")) return { label: "Alexa", detail: pkg };
      if (pkg) return { label: "System", detail: pkg };
    } catch { /* ignore */ }
  }
  return { label };
}

export function stopVoiceListening(): void {
  for (const l of activeListeners) {
    try { l.remove(); } catch { /* */ }
  }
  activeListeners = [];

  if (Platform.OS === "web") {
    try { webRecognition?.stop(); } catch { /* */ }
    webRecognition = null;
    return;
  }

  const mod = getSpeechModule();
  if (!mod) return;
  try { mod.abort(); } catch {
    try { mod.stop(); } catch { /* */ }
  }
}

export type StartListeningOpts = {
  locale: string;
  onResult: (transcript: string) => void;
  onError: (code: string) => void;
  onEnd: () => void;
};

function startWebListening(opts: StartListeningOpts): boolean {
  const root = globalThis as typeof globalThis & {
    SpeechRecognition?: new () => WebRecognition;
    webkitSpeechRecognition?: new () => WebRecognition;
  };
  const Ctor = root.SpeechRecognition || root.webkitSpeechRecognition;
  if (!Ctor) {
    opts.onError("unavailable");
    return false;
  }

  stopVoiceListening();
  const recognition = new Ctor();
  recognition.lang = localeToBcp47(opts.locale);
  recognition.interimResults = false;
  recognition.continuous = false;
  recognition.onresult = (event) => {
    const results = event.results as ArrayLike<{ [j: number]: { transcript?: string } }>;
    const text = Array.from({ length: results.length }, (_, i) => results[i]?.[0]?.transcript ?? "")
      .join(" ")
      .trim();
    if (text) opts.onResult(text);
  };
  recognition.onerror = () => opts.onError("recognition_error");
  recognition.onend = () => {
    webRecognition = null;
    opts.onEnd();
  };
  webRecognition = recognition;
  try {
    recognition.start();
    return true;
  } catch {
    opts.onError("unavailable");
    return false;
  }
}

function startNativeListening(opts: StartListeningOpts): boolean {
  const speech = getSpeechRecognition();
  const mod = speech?.ExpoSpeechRecognitionModule;
  if (!speech || !mod) return false;

  activeListeners.push(
    speech.addSpeechRecognitionListener("result", (event) => {
      const results = event.results as Array<{ transcript?: string }> | undefined;
      const transcript = results?.[0]?.transcript?.trim() ?? "";
      if (!transcript || event.isFinal === false) return;
      opts.onResult(transcript);
    }),
    speech.addSpeechRecognitionListener("error", (event) => {
      const error = String(event.error ?? "");
      if (error === "aborted" || error === "no-speech") return;
      opts.onError(error || "recognition_error");
    }),
    speech.addSpeechRecognitionListener("end", () => opts.onEnd()),
  );

  try {
    mod.start({
      lang: localeToBcp47(opts.locale),
      interimResults: false,
      continuous: false,
      contextualStrings: CONTEXTUAL_PHRASES,
      iosTaskHint: "dictation",
      androidIntentOptions: {
        EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS: 8000,
      },
    });
    return true;
  } catch {
    stopVoiceListening();
    return false;
  }
}

export async function startVoiceListening(opts: StartListeningOpts): Promise<boolean> {
  stopVoiceListening();

  if (Platform.OS === "web") {
    return startWebListening(opts);
  }

  const available = await isVoiceRecognitionAvailable();
  if (!available) {
    opts.onError("unavailable");
    return false;
  }

  const granted = await ensureVoicePermissions();
  if (!granted) {
    opts.onError("permission_denied");
    return false;
  }

  const started = startNativeListening(opts);
  if (!started) opts.onError("unavailable");
  return started;
}

/** Open the system voice assistant where the OS allows (e.g. Google app on Android). */
export async function openPlatformVoiceAssistant(): Promise<boolean> {
  if (Platform.OS !== "android") return false;
  const candidates = [
    "googleapp://voice-search",
    "intent://voice-search#Intent;package=com.google.android.googlequicksearchbox;scheme=googleapp;end",
  ];
  for (const url of candidates) {
    try {
      if (await Linking.canOpenURL(url)) {
        await Linking.openURL(url);
        return true;
      }
    } catch { /* try next */ }
  }
  return false;
}

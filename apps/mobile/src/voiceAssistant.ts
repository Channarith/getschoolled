// Drive Mode voice assistant — uses the device's native speech engine:
//   iOS: SFSpeechRecognizer (same stack as Siri dictation)
//   Android: SpeechRecognizer (Google on most devices)
//   Web: Web Speech API fallback
//
// Third-party apps cannot register a global "Hey Sala" wake word like Hey Siri;
// tap Ask/Mic to speak, optionally prefixed with "Hey Sala" or "Salareen".

import { Linking, Platform } from "react-native";
import {
  addSpeechRecognitionListener,
  ExpoSpeechRecognitionModule,
} from "expo-speech-recognition";

import { localeToBcp47 } from "./tts";

export type VoiceEngineLabel = "Siri" | "Google" | "Alexa" | "System" | "Browser";

const WAKE_RE = /\b(hey\s+sala|sala|salareen)\b/i;

const CONTEXTUAL_PHRASES = [
  "Sala", "Salareen", "Hey Sala", "Hey Salareen",
  "pause", "resume", "continue", "next", "previous", "stop",
  "萨拉", "萨拉丁",
];

type ListenerRemover = { remove: () => void };

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
  try {
    return ExpoSpeechRecognitionModule.isRecognitionAvailable();
  } catch {
    return false;
  }
}

export async function ensureVoicePermissions(): Promise<boolean> {
  if (Platform.OS === "web") return true;
  try {
    const result = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
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
    try {
      const svc = await ExpoSpeechRecognitionModule.getDefaultRecognitionService();
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

  try { ExpoSpeechRecognitionModule.abort(); } catch {
    try { ExpoSpeechRecognitionModule.stop(); } catch { /* */ }
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
  activeListeners.push(
    addSpeechRecognitionListener("result", (event) => {
      const transcript = event.results?.[0]?.transcript?.trim() ?? "";
      if (!transcript || !event.isFinal) return;
      opts.onResult(transcript);
    }),
    addSpeechRecognitionListener("error", (event) => {
      if (event.error === "aborted" || event.error === "no-speech") return;
      opts.onError(event.error || "recognition_error");
    }),
    addSpeechRecognitionListener("end", () => opts.onEnd()),
  );

  try {
    ExpoSpeechRecognitionModule.start({
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

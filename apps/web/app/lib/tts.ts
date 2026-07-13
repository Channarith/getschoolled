// Natural-sounding Web Speech API narration for Drive Mode.
//
// The browser's default voice is usually the robotic one and ignores the
// content language. These helpers (1) map the UI locale to a BCP-47 tag so the
// engine uses the right-accent voice, and (2) pick the best *natural / neural*
// voice the device exposes (Google/Microsoft "Natural"/"Online", Apple
// "Siri"/"Enhanced", etc.) instead of the legacy formant voice. For fully
// human-grade audio, route narration through a neural TTS backend (XTTS / cloud
// TTS via the speech service) — see speakNaturally's `audioUrl` hook.

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
export function scoreVoice(
  v: VoiceLike, lang: string, style: NarrationVoiceStyle = "standard",
): number {
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
  s += voiceNameStyleBonus(style, v.name || "");
  return s;
}

// Pick the best voice matching the target language's primary subtag.
export function pickVoice<T extends VoiceLike>(
  voices: T[], lang: string, style: NarrationVoiceStyle = "standard",
): T | undefined {
  if (!voices || !voices.length) return undefined;
  const primary = lang.split("-")[0].toLowerCase();
  const matches = voices.filter(
    (v) => (v.lang || "").toLowerCase().split("-")[0] === primary,
  );
  const pool = matches.length ? matches : voices;
  return [...pool].sort((a, b) => scoreVoice(b, lang, style) - scoreVoice(a, lang, style))[0];
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
  voiceStyle?: NarrationVoiceStyle;
  rate?: number;
  pitch?: number;
  onend?: () => void;
};

// --------------------------------------------------------------------------- //
// Server neural TTS (ElevenLabs -> edge-tts) with graceful browser fallback.
//
// The speech gateway renders the most natural, culturally-accented audio via
// ElevenLabs when ELEVENLABS_API_KEY is set (else edge-tts neural). We probe
// /tts/status once; when a neural engine is available we fetch + play MP3 audio,
// otherwise we use the on-device Web Speech voice (still picked for naturalness).
let _speechBaseUrl = "";
let _serverTtsReady: boolean | null = null;   // null = unprobed
let _statusProbe: Promise<boolean> | null = null;
let _currentAudio: HTMLAudioElement | null = null;
let _serverVoiceId = "";       // chosen voice_catalog id (accent/language)
let _serverInstructor = "";    // chosen instructor personality id
// Playback epoch: bumped by every cancelSpeech(). A speak() call captures the
// epoch at start; if it changes (Stop/pause/skip/replay/language switch) while
// its neural-audio fetch is still in flight, the resolved audio must NOT start.
// Without this, hitting Stop during a fetch let the *next* segment begin playing
// after the player was already closed.
let _epoch = 0;
let _inflight: AbortController | null = null;

export function configureServerTts(baseUrl: string): void {
  _speechBaseUrl = (baseUrl || "").replace(/\/$/, "");
}

// Select a server neural voice (accent/language) from the voice catalog.
export function setServerVoice(voiceId: string): void {
  _serverVoiceId = voiceId || "";
}

export function getServerVoice(): string {
  return _serverVoiceId;
}

// Select an instructor personality (kind/strict/child/cartoon/…).
export function setServerInstructor(instructorId: string): void {
  _serverInstructor = instructorId || "";
}

export function getServerInstructor(): string {
  return _serverInstructor;
}

async function serverTtsAvailable(): Promise<boolean> {
  if (!_speechBaseUrl) return false;
  if (_serverTtsReady !== null) return _serverTtsReady;
  if (!_statusProbe) {
    _statusProbe = fetch(`${_speechBaseUrl}/tts/status`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { available: false }))
      .then((j) => Boolean(j?.available))
      .catch(() => false)
      .then((ok) => { _serverTtsReady = ok; return ok; });
  }
  return _statusProbe;
}

function stopServerAudio(): void {
  // Abort a fetch that hasn't produced audio yet, so it can't start playing
  // after we've been told to stop.
  if (_inflight) {
    try { _inflight.abort(); } catch { /* */ }
    _inflight = null;
  }
  if (_currentAudio) {
    try { _currentAudio.pause(); } catch { /* */ }
    // Detach handlers first so tearing down the src can't fire onended/onerror
    // (which would call the segment's done() callback).
    _currentAudio.onended = null;
    _currentAudio.onerror = null;
    _currentAudio.src = "";
    _currentAudio = null;
  }
}

// Stop ALL narration (browser utterances AND server audio). Callers that used to
// call window.speechSynthesis.cancel() should call this so server audio also
// stops on pause / skip / replay / language switch. Bumping the epoch also
// invalidates any in-flight neural-audio fetch so it can't start after Stop.
export function cancelSpeech(): void {
  _epoch++;
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    try { window.speechSynthesis.cancel(); } catch { /* */ }
  }
  stopServerAudio();
}

// Fetch one MP3 for the whole text and play it. Resolves true if it played (or
// was cancelled — either way the caller must NOT fall back to the browser),
// false if it could not start for a real reason (then the caller uses the
// browser voice). `myEpoch` is the playback epoch at the time speak() started;
// if it no longer matches we were cancelled and must not start any audio.
async function playServerAudio(
  text: string, opts: SpeakOptions, done: () => void, myEpoch: number,
): Promise<boolean> {
  const ac = new AbortController();
  _inflight = ac;
  try {
    const resp = await fetch(`${_speechBaseUrl}/tts`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        text,
        language: (opts.locale || "en").split("-")[0],
        voice_style: opts.voiceStyle ?? "standard",
        voice: _serverVoiceId,
        instructor: _serverInstructor,
      }),
      signal: ac.signal,
    });
    if (_epoch !== myEpoch) return true;    // cancelled during fetch: swallow
    if (!resp.ok) return false;             // 501/4xx -> browser fallback
    const blob = await resp.blob();
    _inflight = null;                       // fetch fully done; nothing to abort
    if (_epoch !== myEpoch) return true;    // cancelled while reading body
    if (!blob.size) return false;
    const url = URL.createObjectURL(blob);
    stopServerAudio();                      // stop any previous segment's audio
    if (_epoch !== myEpoch) { URL.revokeObjectURL(url); return true; }  // cancelled just now
    const audio = new Audio(url);
    _currentAudio = audio;
    const cleanup = () => { URL.revokeObjectURL(url); if (_currentAudio === audio) _currentAudio = null; };
    // Once the fetch succeeded the server engine works, so a mid-play error
    // should just end this segment (not replay the whole thing via the browser).
    audio.onended = () => { cleanup(); done(); };
    audio.onerror = () => { cleanup(); done(); };
    if (opts.rate && opts.rate > 0) audio.playbackRate = Math.max(0.5, Math.min(2, opts.rate));
    await audio.play();
    return true;
  } catch {
    // Aborted / cancelled: swallow so we don't fall back to the browser voice.
    if (ac.signal.aborted || _epoch !== myEpoch) return true;
    return false;
  } finally {
    if (_inflight === ac) _inflight = null;
  }
}

// --------------------------------------------------------------------------- //
// Chunked streaming voice: synthesize ONE small text chunk into a ready-to-play
// audio "Playable". Used by the real-time pipeline (voicePipeline.ts) so each
// LLM-token chunk is rendered + played immediately for sub-second latency.
// Prefers server neural audio (prefetches the blob now); falls back to the
// on-device voice per chunk.
type Playable = { play: () => Promise<void>; cancel: () => void };

async function _fetchServerAudio(text: string, opts: SpeakOptions): Promise<HTMLAudioElement | null> {
  try {
    const resp = await fetch(`${_speechBaseUrl}/tts`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        text,
        language: (opts.locale || "en").split("-")[0],
        voice_style: opts.voiceStyle ?? "standard",
        voice: _serverVoiceId,
        instructor: _serverInstructor,
      }),
    });
    if (!resp.ok) return null;
    const blob = await resp.blob();
    if (!blob.size) return null;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    if (opts.rate && opts.rate > 0) audio.playbackRate = Math.max(0.5, Math.min(2, opts.rate));
    audio.addEventListener("ended", () => URL.revokeObjectURL(url), { once: true });
    return audio;
  } catch {
    return null;
  }
}

export async function synthChunk(text: string, opts: SpeakOptions): Promise<Playable> {
  const t = (text || "").trim();
  if (!t) return { play: async () => {}, cancel: () => {} };

  if (await serverTtsAvailable()) {
    const audio = await _fetchServerAudio(t, opts);   // prefetched here
    if (audio) {
      return {
        play: () => new Promise<void>((resolve) => {
          audio.onended = () => resolve();
          audio.onerror = () => resolve();
          audio.play().catch(() => resolve());
        }),
        cancel: () => { try { audio.pause(); audio.src = ""; } catch { /* */ } },
      };
    }
  }

  // On-device fallback for this chunk.
  return {
    play: () => new Promise<void>((resolve) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) return resolve();
      const lang = localeToBcp47(opts.locale);
      const style = opts.voiceStyle ?? "standard";
      const u = new SpeechSynthesisUtterance(t);
      u.lang = lang;
      const voice = pickVoice(window.speechSynthesis.getVoices(), lang, style);
      if (voice) u.voice = voice;
      u.rate = opts.rate ?? prosodyForStyle(style).rate;
      u.onend = () => resolve();
      u.onerror = () => resolve();
      window.speechSynthesis.speak(u);
    }),
    cancel: () => { try { window.speechSynthesis.cancel(); } catch { /* */ } },
  };
}

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
  const myEpoch = _epoch;   // invalidated by any cancelSpeech() after this point
  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    opts.onend?.();
  };

  // Prefer server neural audio (ElevenLabs / edge-tts) when available; fall back
  // to the on-device voice on any failure so narration never silently stops.
  serverTtsAvailable().then((ok) => {
    if (finished || _epoch !== myEpoch) return;   // cancelled before we started
    if (ok) {
      playServerAudio(text, opts, done, myEpoch).then((played) => {
        if (!played && !finished && _epoch === myEpoch) speakBrowser(text, opts, done, myEpoch);
      });
    } else {
      speakBrowser(text, opts, done, myEpoch);
    }
  }).catch(() => { if (!finished && _epoch === myEpoch) speakBrowser(text, opts, done, myEpoch); });
}

// On-device Web Speech narration (the natural-voice fallback).
function speakBrowser(text: string, opts: SpeakOptions, done: () => void, myEpoch: number): void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    done();
    return;
  }
  if (_epoch !== myEpoch) return;   // cancelled between fetch fallback and here
  const synth = window.speechSynthesis;
  const lang = localeToBcp47(opts.locale);
  const style = opts.voiceStyle ?? "standard";
  const prosody = prosodyForStyle(style);
  const voice = pickVoice(synth.getVoices(), lang, style);
  const chunks = splitForSpeech(text);

  if (!chunks.length) {
    done();
    return;
  }
  chunks.forEach((chunk, i) => {
    const u = new SpeechSynthesisUtterance(chunk);
    u.lang = lang;
    if (voice) u.voice = voice;
    // Style-specific prosody; explicit rate/pitch override when set.
    u.rate = opts.rate ?? prosody.rate;
    u.pitch = opts.pitch ?? prosody.pitch;
    if (i === chunks.length - 1) u.onend = done; // resolve after the last chunk
    u.onerror = done;                            // and on cancel/error (once)
    synth.speak(u);
  });
}

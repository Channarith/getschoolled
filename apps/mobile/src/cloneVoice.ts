import AsyncStorage from "@react-native-async-storage/async-storage";

import { getSettings } from "./storage";

// Pre-rendered narration in consented company voices (see tts_bakeoff/demo_voice); mirrors apps/web/app/lib/cloneVoice.ts. Never live cloning: a clip is looked
// up by voice + language + a hash of the exact text, and any miss falls back to the default voice.

export const DEFAULT_VOICE_ID = "default";
export const VOICE_CHOICE_KEY = "aoep_demo_voice";

/** "1" when the learner picked an edge voice on purpose, "0" when they picked the Salane Voice on purpose; absent for anyone who never used the picker. */
export const EXPLICIT_VOICE_KEY = "aoep_voice_explicit";
/** Ids the app itself writes to follow the language (englishVariety.ts): never a deliberate choice unless the marker says so. */
const AUTO_FOLLOW_VOICES = new Set(["en_us_f", "en_us_m", "en_gb_f", "en_gb_m", "en_au_f", "en_au_m", "en_sg_f", "en_sg_m"]);

export type CloneVoice = {
  id: string; label: string; ai_label: string; active: boolean; gender?: "male" | "female"; stylized?: boolean;
  /** The bare name ("Sage"): the picker writes "Salane Voice (Sage)" for the default. */
  name?: string;
  /** Language the voice was recorded or designed in ("en", "yue"): choosing it sets the app language to this one. */
  primary_lang?: string;
  /** The Salane Voice for anyone who never chose another (exactly one published voice carries it). */
  default?: boolean;
  kind?: "stock";
};

const ASSETS = "https://salareen-prod.sjc1.vultrobjects.com/voice-assets";   // Vultr Object Storage, published by scripts/sync_voice_assets.sh
const WS = /[ \t\n\r\f\v\u00a0\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/g;

// cyrb53 over UTF-16 code units; must stay identical to tts_bakeoff/demo_voice/clip_hash.py (shared test vectors).
export function clipHash(lang: string, text: string): string {
  const primary = (lang || "en").split(/[-_]/)[0].toLowerCase();
  const s = `${primary}\u241f${(text || "").normalize("NFC").replace(WS, " ").trim()}`;
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < s.length; i++) {
    const ch = s.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16).padStart(14, "0");
}

let voicesPromise: Promise<CloneVoice[]> | null = null;
const indexes = new Map<string, Promise<{ ext: string; clips: Record<string, string[]> } | null>>();

/** Consented voices that are switched on right now. [] when the assets are not published (the selector then hides). */
export function loadCloneVoices(): Promise<CloneVoice[]> {
  if (!voicesPromise) {
    voicesPromise = fetch(`${ASSETS}/voices.json`, { headers: { "cache-control": "no-cache" } })
      .then((r) => (r.ok ? r.json() : { voices: [] }))
      .then((j) => (Array.isArray(j?.voices) ? (j.voices as CloneVoice[]).filter((v) => v.active) : []))
      .catch(() => []);
  }
  return voicesPromise;
}

/** The raw saved choice for the pickers ("default" when none was saved): see resolveSelectedVoice for what actually narrates. */
export async function getSelectedVoice(): Promise<string> {
  try { return (await AsyncStorage.getItem(VOICE_CHOICE_KEY)) || DEFAULT_VOICE_ID; } catch { return DEFAULT_VOICE_ID; }
}

export async function setSelectedVoice(id: string): Promise<void> {
  try { await AsyncStorage.setItem(VOICE_CHOICE_KEY, id); } catch { /* storage unavailable */ }
}

/** The edge voice the learner deliberately chose ("" when none): an id the app wrote to follow the language does not count. */
export async function explicitEdgeVoice(): Promise<string> {
  try {
    const voice = (await getSettings()).voiceId || "";
    if (!voice) return "";
    const marker = (await AsyncStorage.getItem(EXPLICIT_VOICE_KEY)) || "";
    if (marker === "1") return voice;
    if (marker === "0") return "";
    return AUTO_FOLLOW_VOICES.has(voice) ? "" : voice;
  } catch { return ""; }
}

export async function setExplicitEdgeVoice(on: boolean): Promise<void> {
  try { await AsyncStorage.setItem(EXPLICIT_VOICE_KEY, on ? "1" : "0"); } catch { /* storage unavailable */ }
}

/** The Salane Voice for anyone who never chose one: the published voice flagged default (Sage), or null. */
export function defaultCloneVoice(voices: CloneVoice[]): CloneVoice | null {
  return voices.find((v) => v.active && v.default) ?? null;
}

/** "Salane Voice (Sage)" for the default voice; plain "Salane Voice" when none is published (offline, nothing cleared). */
export function salaneVoiceLabel(voices: CloneVoice[]): string {
  const d = defaultCloneVoice(voices);
  const name = d ? (d.name || d.label).replace(/\s*\(designed\)\s*$/i, "").trim() : "";
  return name ? `Salane Voice (${name})` : "Salane Voice";
}

/** Same rules as resolveVoice in apps/web/app/lib/cloneVoice.ts: a voice picked on purpose (and still published), else the live edge voice
 * when an edge voice or a tone was picked on purpose, else the published default (Sage). A withdrawn or stale id falls through. */
export function resolveVoice(input: { saved: string | null; edgeVoice: string; tone: string; voices: CloneVoice[] }): string {
  const { saved, edgeVoice, tone, voices } = input;
  if (saved && saved !== DEFAULT_VOICE_ID && voices.some((v) => v.active && v.id === saved)) return saved;
  if (edgeVoice) return DEFAULT_VOICE_ID;
  if (tone && tone !== "neutral") return DEFAULT_VOICE_ID;
  return defaultCloneVoice(voices)?.id ?? DEFAULT_VOICE_ID;
}

const VOICES_WAIT_MS = 1500;

/** The narration voice right now (see resolveVoice). Never rejects; a slow voices.json costs at most a moment. */
export async function resolveSelectedVoice(): Promise<string> {
  const voices = await Promise.race([
    loadCloneVoices(),
    new Promise<CloneVoice[]>((resolve) => setTimeout(() => resolve([]), VOICES_WAIT_MS)),
  ]).catch(() => [] as CloneVoice[]);
  let saved: string | null = null;
  try { saved = (await AsyncStorage.getItem(VOICE_CHOICE_KEY)) || null; } catch { /* storage unavailable */ }
  return resolveVoice({ saved, edgeVoice: await explicitEdgeVoice(), tone: "", voices });
}

/** Gender of the narration voice ("male" | "female"), or "" for the live edge voice. A line without a clip falls back to this gender. */
export async function selectedCloneGender(): Promise<"male" | "female" | ""> {
  const id = await resolveSelectedVoice();
  if (id === DEFAULT_VOICE_ID) return "";
  const voice = (await loadCloneVoices()).find((v) => v.id === id);
  return voice?.gender === "male" || voice?.gender === "female" ? voice.gender : "";
}

function loadIndex(voice: string) {
  if (!indexes.has(voice)) {
    indexes.set(voice, fetch(`${ASSETS}/${encodeURIComponent(voice)}/index.json`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null));
  }
  return indexes.get(voice)!;
}

/** Language codes this voice has published clips for (empty when the voice has no index yet). */
export async function cloneVoiceLanguages(voice: string): Promise<string[]> {
  const index = await loadIndex(voice);
  return index ? Object.keys(index.clips || {}).filter((l) => (index.clips?.[l] || []).length > 0) : [];
}

export function resetCloneVoiceCacheForTests(): void {
  voicesPromise = null;
  indexes.clear();
}

/** URL of the pre-rendered clip for the selected voice, or null (default voice, voice switched off, or no such clip). */
export async function cloneClipUrl(lang: string, text: string, voice?: string): Promise<string | null> {
  if (!text.trim()) return null;
  voice = voice ?? (await resolveSelectedVoice());   // no explicit voice: the learner's choice, else the published default (Sage)
  if (!voice || voice === DEFAULT_VOICE_ID) return null;
  const active = (await loadCloneVoices()).some((v) => v.id === voice);   // consent revoked => not listed => no clip
  if (!active) return null;
  const index = await loadIndex(voice);
  if (!index) return null;
  const l = (lang || "en").split(/[-_]/)[0].toLowerCase();
  const h = clipHash(l, text);
  if (index.clips?.[l]?.includes(h)) return `${ASSETS}/${encodeURIComponent(voice)}/${l}/${h}.${index.ext || "mp3"}`;
  return null;
}

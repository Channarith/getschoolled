// Pre-rendered narration in consented company voices (see tts_bakeoff/demo_voice). Never live cloning: a clip is looked
// up by voice + language + a hash of the exact text, and any miss falls back to the default voice.

export const DEFAULT_VOICE_ID = "default";
export const VOICE_CHOICE_KEY = "aoep_demo_voice";
export const VOICE_CHOICE_EVENT = "aoep-demo-voice";

export type CloneVoice = {
  id: string; label: string; ai_label: string; active: boolean; gender?: "male" | "female"; stylized?: boolean;
  /** The bare name ("Sage"): the picker writes "Salane Voice (Sage)" for the default. */
  name?: string;
  /** Language the voice was recorded or designed in ("en", "yue"): choosing it sets the app language to this one. */
  primary_lang?: string;
  /** The Salane Voice for visitors who never chose another (exactly one published voice carries it). */
  default?: boolean;
  kind?: "stock";
};
/** The edge-tts voice id and tone the account menu saves; read here so the default knows when the visitor chose something else. */
export const EDGE_VOICE_KEY = "aoep_drive_voice";
export const TONE_KEY = "aoep_demo_tone";
/** "1" when the visitor picked an edge voice on purpose, "0" when they picked the Salane Voice on purpose; absent for visitors who never used the picker. */
export const EXPLICIT_VOICE_KEY = "aoep_voice_explicit";
/** Ids the app itself writes to follow the language (englishVariety.ts): never a deliberate choice unless the marker says so. */
const AUTO_FOLLOW_VOICES = new Set(["en_us_f", "en_us_m", "en_gb_f", "en_gb_m", "en_au_f", "en_au_m", "en_sg_f", "en_sg_m"]);

const ASSETS = (process.env.NEXT_PUBLIC_VOICE_ASSETS_URL || "/voice-assets").replace(/\/$/, "");
/** Where the published clips live; the course-studio frame gets it as a URL parameter so its narration finds the same clips. */
export const VOICE_ASSETS_BASE = ASSETS;
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
    voicesPromise = fetch(`${ASSETS}/voices.json`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { voices: [] }))
      .then((j) => (Array.isArray(j?.voices) ? (j.voices as CloneVoice[]).filter((v) => v.active) : []))
      .catch(() => []);
  }
  return voicesPromise;
}

/** The Salane Voice for visitors who never chose one: the published voice flagged default (Sage), or null. */
export function defaultCloneVoice(voices: CloneVoice[]): CloneVoice | null {
  return voices.find((v) => v.active && v.default) ?? null;
}

/** "Salane Voice (Sage)" for the default voice; plain "Salane Voice" when none is published (offline, nothing cleared). */
export function salaneVoiceLabel(voices: CloneVoice[]): string {
  const d = defaultCloneVoice(voices);
  const name = d ? (d.name || d.label).replace(/\s*\(designed\)\s*$/i, "").trim() : "";
  return name ? `Salane Voice (${name})` : "Salane Voice";
}

/**
 * Which pre-rendered voice narrates, as a company-voice id, or DEFAULT_VOICE_ID for the live edge-tts voice.
 *   1. a voice the visitor picked on purpose (and that is still published: a withdrawn or stale id falls through);
 *   2. an edge-tts voice picked on purpose, or a tone (the pre-rendered default is the plain voice), means the live edge voice;
 *   3. otherwise the published default (Sage), so a visitor who never chose gets it, and so does one whose stored choice was the old
 *      automatic voice ("default"); with nothing published it is the live edge voice.
 * A line the chosen voice has no clip for still falls back to an edge voice of the SAME gender and language (see tts.ts).
 */
export function resolveVoice(input: { saved: string | null; edgeVoice: string; tone: string; voices: CloneVoice[] }): string {
  const { saved, edgeVoice, tone, voices } = input;
  if (saved && saved !== DEFAULT_VOICE_ID && voices.some((v) => v.active && v.id === saved)) return saved;
  if (edgeVoice) return DEFAULT_VOICE_ID;
  if (tone && tone !== "neutral") return DEFAULT_VOICE_ID;
  return defaultCloneVoice(voices)?.id ?? DEFAULT_VOICE_ID;
}

function readStored(key: string): string {
  try { return localStorage.getItem(key) || ""; } catch { return ""; }
}

/** The edge voice the visitor deliberately chose ("" when none): a stored id the app wrote to follow the language does not count. */
export function explicitEdgeVoice(): string {
  const voice = readStored(EDGE_VOICE_KEY);
  if (!voice) return "";
  const marker = readStored(EXPLICIT_VOICE_KEY);
  if (marker === "1") return voice;
  if (marker === "0") return "";
  return AUTO_FOLLOW_VOICES.has(voice) ? "" : voice;
}

export function setExplicitEdgeVoice(on: boolean): void {
  try { localStorage.setItem(EXPLICIT_VOICE_KEY, on ? "1" : "0"); } catch { /* private mode */ }
}

/** The stored company-voice choice, or null when the visitor never chose ("default" means the old automatic voice). */
export function getStoredVoiceChoice(): string | null {
  if (typeof window === "undefined") return null;
  return readStored(VOICE_CHOICE_KEY) || null;
}

/** How long a slow or blocked voices.json may delay the first narrated line before the live edge voice speaks instead. */
const VOICES_WAIT_MS = 1500;

/** The narration voice right now (see resolveVoice). Never rejects. */
export async function resolveSelectedVoice(): Promise<string> {
  if (typeof window === "undefined") return DEFAULT_VOICE_ID;
  const voices = await Promise.race([
    loadCloneVoices(),
    new Promise<CloneVoice[]>((resolve) => setTimeout(() => resolve([]), VOICES_WAIT_MS)),
  ]).catch(() => [] as CloneVoice[]);
  return resolveVoice({ saved: getStoredVoiceChoice(), edgeVoice: explicitEdgeVoice(), tone: readStored(TONE_KEY), voices });
}

/** Gender of the narration voice ("male" | "female"), or "" for the live edge voice or an unpublished gender. */
export async function selectedCloneGender(): Promise<"male" | "female" | ""> {
  const id = await resolveSelectedVoice();
  if (id === DEFAULT_VOICE_ID) return "";
  const voice = (await loadCloneVoices()).find((v) => v.id === id);
  return voice?.gender === "male" || voice?.gender === "female" ? voice.gender : "";
}

/** The raw saved choice for the pickers ("default" when none was saved): see resolveSelectedVoice for what actually narrates. */
export function getSelectedVoice(): string {
  if (typeof window === "undefined") return DEFAULT_VOICE_ID;
  try { return localStorage.getItem(VOICE_CHOICE_KEY) || DEFAULT_VOICE_ID; } catch { return DEFAULT_VOICE_ID; }
}

export function setSelectedVoice(id: string): void {
  try { localStorage.setItem(VOICE_CHOICE_KEY, id); } catch { /* private mode */ }
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(VOICE_CHOICE_EVENT, { detail: id }));
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

const misses = new Set<string>();

export function resetCloneVoiceCacheForTests(): void {
  salaneIndexPromise = null;
  voicesPromise = null;
  indexes.clear();
  misses.clear();
}

/** URL of the pre-rendered clip for the selected voice, or null (default voice, voice switched off, or no such clip). */
export async function cloneClipUrl(lang: string, text: string, voice?: string): Promise<string | null> {
  if (!text.trim()) return null;
  voice = voice ?? await resolveSelectedVoice();   // no explicit voice: the visitor's choice, else the published default (Sage)
  if (!voice || voice === DEFAULT_VOICE_ID) return null;
  const active = (await loadCloneVoices()).some((v) => v.id === voice);   // consent revoked => not listed => no clip
  if (!active) return null;
  const index = await loadIndex(voice);
  if (!index) return null;
  const l = (lang || "en").split(/[-_]/)[0].toLowerCase();
  const h = clipHash(l, text);
  if (index.clips?.[l]?.includes(h)) return `${ASSETS}/${encodeURIComponent(voice)}/${l}/${h}.${index.ext || "mp3"}`;
  const key = `${l}:${h}`;
  if (!misses.has(key)) {
    misses.add(key);
    // Lets a developer paste window.__cloneVoiceMisses into tts_bakeoff.demo_voice.manifest --extra-texts.
    if (typeof window !== "undefined") ((window as unknown as { __cloneVoiceMisses?: object[] }).__cloneVoiceMisses ||= []).push({ demo: "miss", lang: l, text });
  }
  return null;
}

// ---- Home-page mascot narration --------------------------------------------------------------------------------
// Pre-rendered clips, never the browser's built-in voice unless a clip is missing. The default voice is Salane
// (edge-tts) clips shipped under /landing-voice; a visitor who picked a consented company voice in the voice picker
// gets that voice's clip for the same line when it has one.
export const LANDING_VOICE_BASE = "/landing-voice/salane";

type SalaneIndex = { ext?: string; clips?: Record<string, string[]> };
let salaneIndexPromise: Promise<SalaneIndex | null> | null = null;

function loadSalaneIndex(): Promise<SalaneIndex | null> {
  if (!salaneIndexPromise) {
    salaneIndexPromise = fetch(`${LANDING_VOICE_BASE}/index.json`)
      .then((r) => (r.ok ? (r.json() as Promise<SalaneIndex>) : null))
      .catch(() => null);
  }
  return salaneIndexPromise;
}

/** URL of the clip to play for this line: the chosen consented voice, else the Salane clip, else null (caller falls back). */
export async function landingClipUrl(lang: string, text: string, voice?: string): Promise<string | null> {
  const custom = await cloneClipUrl(lang, text, voice).catch(() => null);
  if (custom) return custom;
  const index = await loadSalaneIndex();
  if (!index) return null;
  const l = (lang || "en").split(/[-_]/)[0].toLowerCase();
  const h = clipHash(l, text);
  return index.clips?.[l]?.includes(h) ? `${LANDING_VOICE_BASE}/${l}/${h}.${index.ext || "mp3"}` : null;
}

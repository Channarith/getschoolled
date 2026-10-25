import AsyncStorage from "@react-native-async-storage/async-storage";

// Pre-rendered narration in consented company voices (see tts_bakeoff/demo_voice); mirrors apps/web/app/lib/cloneVoice.ts. Never live cloning: a clip is looked
// up by voice + language + a hash of the exact text, and any miss falls back to the default voice.

export const DEFAULT_VOICE_ID = "default";
export const VOICE_CHOICE_KEY = "aoep_demo_voice";

export type CloneVoice = { id: string; label: string; ai_label: string; active: boolean };

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

export async function getSelectedVoice(): Promise<string> {
  try { return (await AsyncStorage.getItem(VOICE_CHOICE_KEY)) || DEFAULT_VOICE_ID; } catch { return DEFAULT_VOICE_ID; }
}

export async function setSelectedVoice(id: string): Promise<void> {
  try { await AsyncStorage.setItem(VOICE_CHOICE_KEY, id); } catch { /* storage unavailable */ }
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
  voice = voice ?? (await getSelectedVoice());
  if (!voice || voice === DEFAULT_VOICE_ID || !text.trim()) return null;
  const active = (await loadCloneVoices()).some((v) => v.id === voice);   // consent revoked => not listed => no clip
  if (!active) return null;
  const index = await loadIndex(voice);
  if (!index) return null;
  const l = (lang || "en").split(/[-_]/)[0].toLowerCase();
  const h = clipHash(l, text);
  if (index.clips?.[l]?.includes(h)) return `${ASSETS}/${encodeURIComponent(voice)}/${l}/${h}.${index.ext || "mp3"}`;
  return null;
}

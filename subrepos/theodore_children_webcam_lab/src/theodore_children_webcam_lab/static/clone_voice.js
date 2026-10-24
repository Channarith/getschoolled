// Pre-rendered narration in consented company voices (tts_bakeoff/demo_voice). A clip is found by voice + language + a hash of the
// exact spoken text; any miss falls back to the default voice. Hash must match clip_hash.py / apps/web/app/lib/cloneVoice.ts.
export const DEFAULT_VOICE_ID = "default";
const KEY = "aoep_demo_voice";
const ASSETS = String((typeof window !== "undefined" && window.CLONE_VOICE_ASSETS) || "https://salareen-prod.sjc1.vultrobjects.com/voice-assets").replace(/\/$/, "");
const WS = /[ \t\n\r\f\v\u00a0\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/g;

export function clipHash(lang, text) {
  const primary = String(lang || "en").split(/[-_]/)[0].toLowerCase();
  const s = `${primary}\u241f${String(text || "").normalize("NFC").replace(WS, " ").trim()}`;
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
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

let voicesP = null;
const indexes = new Map();
export function resetForTests() { voicesP = null; indexes.clear(); }

export function loadCloneVoices() {
  voicesP ||= fetch(`${ASSETS}/voices.json`, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : { voices: [] }))
    .then((j) => (Array.isArray(j?.voices) ? j.voices.filter((v) => v.active) : []))
    .catch(() => []);
  return voicesP;
}

export function selectedVoice() {
  try { return localStorage.getItem(KEY) || DEFAULT_VOICE_ID; } catch (_) { return DEFAULT_VOICE_ID; }
}

export async function cloneClipUrl(lang, text, voice = selectedVoice()) {
  if (!voice || voice === DEFAULT_VOICE_ID || !String(text || "").trim()) return null;
  if (!(await loadCloneVoices()).some((v) => v.id === voice)) return null;   // consent revoked => unlisted => no clip
  if (!indexes.has(voice)) {
    indexes.set(voice, fetch(`${ASSETS}/${encodeURIComponent(voice)}/index.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null));
  }
  const index = await indexes.get(voice);
  const l = String(lang || "en").split(/[-_]/)[0].toLowerCase();
  const h = clipHash(l, text);
  return index?.clips?.[l]?.includes(h) ? `${ASSETS}/${encodeURIComponent(voice)}/${l}/${h}.${index.ext || "mp3"}` : null;
}

/** Fill #clone-voice-slot with the narrator picker; stays empty until a consented voice is published. */
export async function mountVoiceSelect(slot = document.getElementById("clone-voice-slot")) {
  if (!slot) return;
  const voices = await loadCloneVoices();
  if (!voices.length) return;
  const cur = voices.some((v) => v.id === selectedVoice()) ? selectedVoice() : DEFAULT_VOICE_ID;
  const select = document.createElement("select");
  select.setAttribute("aria-label", "Narrator voice");
  select.innerHTML = `<option value="${DEFAULT_VOICE_ID}">Salane (default)</option>` + voices.map((v) => `<option value="${v.id}"></option>`).join("");
  [...select.options].slice(1).forEach((o, i) => { o.textContent = voices[i].label; });
  select.value = cur;
  const note = document.createElement("small");
  const showNote = () => { note.textContent = voices.find((v) => v.id === select.value)?.ai_label || ""; };
  select.addEventListener("change", () => { try { localStorage.setItem(KEY, select.value); } catch (_) { /* private mode */ } showNote(); });
  showNote();
  slot.append(select, note);
}

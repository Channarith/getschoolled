// Voice tone (professional, cute, anime, ...) for the edge-tts voices. Mirrors aoep_shared.tone_presets: the ids are the same strings the
// speech gateway and the course studio accept as `tone`, and the same ones the pre-rendered clips are named after (edge.<Voice>~<tone>).
// A consented company voice can only take a tone with its own signed "stylized versions" consent, which no voice has today, so the picker
// disables the tone for those voices (see toneBlockedForVoice).

export const TONE_KEY = "aoep_demo_tone";
export const TONE_EVENT = "aoep-demo-tone";
export const NEUTRAL_TONE = "neutral";

export type ToneOption = { id: string; label: string };

const PRESET_LABELS: [string, string][] = [
  ["professional", "Professional"], ["cute", "Cute"], ["anime", "Anime"], ["warm", "Warm"], ["calm", "Calm"],
  ["energetic", "Energetic"], ["tough", "Tough"], ["heavy", "Heavy"], ["light", "Light"],
];
const PARTS = ["professional", "cute", "anime"];
const SHORT: Record<string, string> = { professional: "Pro" };
const nice = (p: string) => SHORT[p] ?? p[0].toUpperCase() + p.slice(1);

export const TONES: ToneOption[] = [{ id: NEUTRAL_TONE, label: "Neutral" }, ...PRESET_LABELS.map(([id, label]) => ({ id, label }))];

/** The 13 blends: each pair of professional / cute / anime at 75-25, 50-50 and 25-75, an even three-way mix and three leaning mixes. */
export const MIX_TONES: ToneOption[] = (() => {
  const out: ToneOption[] = [];
  for (let i = 0; i < PARTS.length; i++) {
    for (let j = i + 1; j < PARTS.length; j++) {
      for (const w of [75, 50, 25]) {
        out.push({ id: `blend-${PARTS[i]}${w}-${PARTS[j]}${100 - w}`, label: `${nice(PARTS[i])} ${w} / ${nice(PARTS[j])} ${100 - w}` });
      }
    }
  }
  out.push({ id: "blend-pro34-cute33-anime33", label: "Pro / Cute / Anime (even)" });
  out.push({ id: "blend-pro60-cute20-anime20", label: "Mostly Pro" });
  out.push({ id: "blend-cute60-pro20-anime20", label: "Mostly Cute" });
  out.push({ id: "blend-anime60-pro20-cute20", label: "Mostly Anime" });
  return out;
})();

const KNOWN = new Set([...TONES, ...MIX_TONES].map((t) => t.id));

export function isKnownTone(id: string | null | undefined): boolean {
  return !!id && KNOWN.has(id);
}

/** The saved tone id, or "" for the plain voice (neutral, nothing saved, or an id this build does not know). */
export function getTone(): string {
  if (typeof window === "undefined") return "";
  try {
    const t = localStorage.getItem(TONE_KEY) || "";
    return t !== NEUTRAL_TONE && isKnownTone(t) ? t : "";
  } catch { return ""; }
}

export function setTone(id: string): void {
  const next = isKnownTone(id) ? id : NEUTRAL_TONE;
  try { localStorage.setItem(TONE_KEY, next); } catch { /* private mode */ }
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(TONE_EVENT, { detail: next }));
}

/** True when the selected company voice may not take a tone (no signed stylized-versions consent for it). */
export function toneBlockedForVoice(voice: { stylized?: boolean } | null | undefined): boolean {
  return !!voice && voice.stylized !== true;
}

export const TONE_BLOCKED_TIP = "Tones need a separate signed consent for this voice, so they are off for it. Pick an edge voice to use a tone.";

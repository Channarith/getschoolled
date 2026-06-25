// Persisted narration voice preference for Drive Mode (web).

import type { NarrationVoicePref } from "./voiceProfiles";

const KEY = "aoep_narration_voice_v1";

export function getNarrationVoicePref(): NarrationVoicePref {
  if (typeof window === "undefined") return "auto";
  try {
    const raw = localStorage.getItem(KEY);
    if (raw === "auto" || raw === "standard" || raw === "child"
        || raw === "accessible" || raw === "calm" || raw === "clear") {
      return raw;
    }
  } catch { /* */ }
  return "auto";
}

export function setNarrationVoicePref(pref: NarrationVoicePref): void {
  try {
    localStorage.setItem(KEY, pref);
  } catch { /* */ }
}

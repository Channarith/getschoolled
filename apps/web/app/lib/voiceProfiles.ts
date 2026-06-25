// Narration voice styles — mirrors packages/shared aoep_shared.voice_profiles.

import type { StudentProfile } from "./api";

export type NarrationVoiceStyle = "standard" | "child" | "accessible" | "calm" | "clear";
export type NarrationVoicePref = "auto" | NarrationVoiceStyle;

export const NARRATION_VOICE_STYLES: NarrationVoiceStyle[] = [
  "standard", "child", "accessible", "calm", "clear",
];

export const NARRATION_VOICE_LABELS: Record<NarrationVoiceStyle, string> = {
  standard: "Standard",
  child: "Child-friendly",
  accessible: "Accessible (slower)",
  calm: "Calm & gentle",
  clear: "Clear & crisp",
};

export type VoiceProsody = { rate: number; pitch: number };

export function prosodyForStyle(style: NarrationVoiceStyle): VoiceProsody {
  switch (style) {
    case "child": return { rate: 0.88, pitch: 1.12 };
    case "accessible": return { rate: 0.78, pitch: 1.0 };
    case "calm": return { rate: 0.85, pitch: 0.95 };
    case "clear": return { rate: 0.92, pitch: 1.0 };
    default: return { rate: 0.95, pitch: 1.0 };
  }
}

export function suggestVoiceStyleFromProfile(student?: Partial<StudentProfile> | null): NarrationVoiceStyle {
  if (!student) return "standard";
  if (student.age_band === "child") return "child";
  const acc = student.accessibility || {};
  if (acc.needs_extra_time || student.learning_pace === "slow" || student.reading_level === "beginner") {
    return "accessible";
  }
  if (acc.uses_assistive_tech || acc.needs_captions) return "clear";
  if (student.age_band === "teen") return "clear";
  return "standard";
}

export function resolveVoiceStyle(
  pref: NarrationVoicePref,
  student?: Partial<StudentProfile> | null,
): NarrationVoiceStyle {
  if (pref !== "auto") return pref;
  return suggestVoiceStyleFromProfile(student);
}

export function voiceNameStyleBonus(style: NarrationVoiceStyle, voiceName: string): number {
  const name = (voiceName || "").toLowerCase();
  if (style === "child") {
    if (/(child|kids|junior|nicky|pip|zoe)/.test(name)) return 6;
    if (name.includes("compact")) return 2;
  }
  if (style === "accessible") {
    if (/(enhanced|natural|neural|premium|siri)/.test(name)) return 4;
  }
  if (style === "calm") {
    if (/(samantha|karen|serena|moira|tessa)/.test(name)) return 3;
  }
  if (style === "clear") {
    if (/(enhanced|natural|neural|wavenet|jenny|guy)/.test(name)) return 5;
  }
  if (/(albert|zarvox|whisper|jester|bahh)/.test(name)) return -8;
  return 0;
}

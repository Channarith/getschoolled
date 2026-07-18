// Unified voice & instructor preferences — shared by Drive Mode, live rooms,
// lessons, and class narration (web). Narration Voice style chips were removed;
// prosody is derived from instructor personality or the learning profile (auto).

export type VoiceGenderPref = "any" | "female" | "male";

export type VoicePrefs = {
  voiceId: string;
  instructorId: string;
  voiceGender: VoiceGenderPref;
};

const VOICE_KEY = "aoep_drive_voice";
const INSTRUCTOR_KEY = "aoep_drive_instructor";
const GENDER_KEY = "aoep_drive_gender";

export function getVoicePrefs(): VoicePrefs {
  if (typeof window === "undefined") {
    return { voiceId: "", instructorId: "", voiceGender: "any" };
  }
  try {
    const voiceId = localStorage.getItem(VOICE_KEY) || "";
    const instructorId = localStorage.getItem(INSTRUCTOR_KEY) || "";
    const g = localStorage.getItem(GENDER_KEY) || "";
    const voiceGender: VoiceGenderPref =
      g === "male" || g === "female" ? g : "any";
    return { voiceId, instructorId, voiceGender };
  } catch {
    return { voiceId: "", instructorId: "", voiceGender: "any" };
  }
}

export function setVoicePrefs(patch: Partial<VoicePrefs>): VoicePrefs {
  const cur = getVoicePrefs();
  const next = { ...cur, ...patch };
  try {
    if (patch.voiceId !== undefined) {
      localStorage.setItem(VOICE_KEY, patch.voiceId);
    }
    if (patch.instructorId !== undefined) {
      localStorage.setItem(INSTRUCTOR_KEY, patch.instructorId);
    }
    if (patch.voiceGender !== undefined) {
      localStorage.setItem(GENDER_KEY, patch.voiceGender);
    }
  } catch { /* private mode */ }
  return next;
}

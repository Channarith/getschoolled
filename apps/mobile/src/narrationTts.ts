// Apply unified voice/instructor prefs before any narration (Drive, live room,
// lessons). Mobile Settings owns voice & accent + instructor personality;
// prosody is derived from instructor or the learning profile (internal auto).

import {
  getTtsVoices, listStudents, SPEECH_URL,
  type StudentProfile, type VoiceGroup,
} from "./api";
import { getSettings, type Settings } from "./storage";
import {
  configureServerTts, setServerInstructor, setServerVoice, type SpeakOptions,
} from "./tts";
import { prosodyForStyle, resolveEffectiveVoiceStyle } from "./voiceProfiles";

export type VoiceGenderPref = "any" | "female" | "male";

export type VoicePrefs = {
  voiceId: string;
  instructorId: string;
  voiceGender: VoiceGenderPref;
};

let voiceGroupsCache: VoiceGroup[] | null = null;

export function voicePrefsFromSettings(s: Settings): VoicePrefs {
  return {
    voiceId: s.voiceId || "",
    instructorId: s.instructorId || "",
    voiceGender: s.voiceGender || "any",
  };
}

export async function loadVoicePrefsFromSettings(): Promise<VoicePrefs> {
  return voicePrefsFromSettings(await getSettings());
}

export async function loadVoiceCatalog(): Promise<VoiceGroup[]> {
  if (voiceGroupsCache) return voiceGroupsCache;
  try {
    voiceGroupsCache = (await getTtsVoices()).groups;
  } catch {
    voiceGroupsCache = [];
  }
  return voiceGroupsCache;
}

export function applyVoicePrefsToTts(prefs: VoicePrefs): void {
  configureServerTts(SPEECH_URL);
  setServerVoice(prefs.voiceId);
  setServerInstructor(prefs.instructorId);
}

export function accentFromPrefs(
  prefs: VoicePrefs,
  groups: VoiceGroup[],
): { voiceLocale: string; voiceGender: string } {
  const v = groups.flatMap((g) => g.voices).find((x) => x.id === prefs.voiceId);
  const voiceGender =
    prefs.voiceGender !== "any" ? prefs.voiceGender : (v?.gender || "");
  return { voiceLocale: v?.locale || "", voiceGender };
}

export type NarrationSpeakBase = Pick<
  SpeakOptions,
  "locale" | "voiceStyle" | "voiceLocale" | "voiceGender" | "persona"
>;

export async function buildNarrationSpeakOptions(
  locale: string,
  student?: StudentProfile | null,
): Promise<NarrationSpeakBase> {
  const prefs = await loadVoicePrefsFromSettings();
  applyVoicePrefsToTts(prefs);
  const groups = await loadVoiceCatalog();
  const { voiceLocale, voiceGender } = accentFromPrefs(prefs, groups);
  const voiceStyle = resolveEffectiveVoiceStyle(prefs.instructorId, student);
  return {
    locale,
    voiceStyle,
    voiceLocale: voiceLocale || undefined,
    voiceGender: voiceGender || undefined,
    persona: prefs.instructorId || undefined,
  };
}

export async function fetchStudentForVoice(): Promise<StudentProfile | null> {
  try {
    return (await listStudents()).students[0] ?? null;
  } catch {
    return null;
  }
}

export function prosodyRateMultiplier(
  voiceStyle: ReturnType<typeof resolveEffectiveVoiceStyle>,
): number {
  return prosodyForStyle(voiceStyle).rate;
}

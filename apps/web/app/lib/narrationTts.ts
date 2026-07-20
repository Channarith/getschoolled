// Apply unified voice/instructor prefs before any narration (Drive, live room,
// lessons, class). Ensures neural TTS is configured and speak options match
// Settings / Drive voice pickers everywhere.

import { getTtsVoices, listStudents, SPEECH_URL, type StudentProfile, type VoiceGroup } from "./api";
import {
  configureServerTts, setServerInstructor, setServerVoice, type SpeakOptions,
} from "./tts";
import { getVoicePrefs, type VoiceGenderPref, type VoicePrefs } from "./voicePrefs";
import { prosodyForStyle, resolveEffectiveVoiceStyle } from "./voiceProfiles";

let voiceGroupsCache: VoiceGroup[] | null = null;

export async function loadVoiceCatalog(): Promise<VoiceGroup[]> {
  if (voiceGroupsCache !== null) return voiceGroupsCache;
  try {
    voiceGroupsCache = (await getTtsVoices()).groups;
  } catch {
    // Leave cache as null so the next call retries; setting it to [] (truthy)
    // would permanently suppress future retries even if the endpoint recovers.
    return [];
  }
  return voiceGroupsCache;
}

export function applyVoicePrefsToTts(prefs: VoicePrefs = getVoicePrefs()): void {
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

/** Build speak options from saved voice/instructor prefs (+ optional student). */
export async function buildNarrationSpeakOptions(
  locale: string,
  student?: Partial<StudentProfile> | null,
): Promise<NarrationSpeakBase> {
  const prefs = getVoicePrefs();
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

/** Fetch the signed-in learner profile for internal auto prosody (best-effort). */
export async function fetchStudentForVoice(): Promise<StudentProfile | null> {
  try {
    return (await listStudents()).students[0] ?? null;
  } catch {
    return null;
  }
}

export function prosodyRateMultiplier(voiceStyle: ReturnType<typeof resolveEffectiveVoiceStyle>): number {
  return prosodyForStyle(voiceStyle).rate;
}

export type { VoiceGenderPref, VoicePrefs };

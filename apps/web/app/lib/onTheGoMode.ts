/** Shared On the Go modes. Demo and the signed-in tab use one component. */

export const ON_THE_GO_DEMO_SECONDS = 10 * 60;

export type OnTheGoMode = "demo" | "full";

export type OnTheGoExperience = {
  mode: OnTheGoMode;
  /** Demo counts down and then stops. The signed-in tab has no timer. */
  showTimer: boolean;
  sampleSeconds: number;
  /** Live Sala agent. Demo narration stays sample-only and does not mint a session. */
  salaAgent: boolean;
  /** Signed-in tab lists the catalog. Demo keeps a single sample course. */
  fullCatalog: boolean;
  /**
   * In demo mode we don't offer a course picker - a single curated AI course
   * is auto-selected so the visitor just has to tap Start. The signed-in tab
   * still shows the search + dropdown.
   */
  showCoursePicker: boolean;
};

export function onTheGoExperience(mode: OnTheGoMode): OnTheGoExperience {
  const demo = mode === "demo";
  return {
    mode,
    showTimer: demo,
    sampleSeconds: demo ? ON_THE_GO_DEMO_SECONDS : 0,
    salaAgent: !demo,
    fullCatalog: !demo,
    showCoursePicker: !demo,
  };
}

/**
 * The single curated audio course the public demo plays. Every topic-based
 * audio lesson in packages/shared/src/aoep_shared/audio_courses.py runs at
 * least MIN_DRIVE_MINUTES (30), so this is comfortably over the demo's
 * 10-minute cap - visitors hear 10 minutes of real material and are stopped
 * at the timer, not mid-sentence.
 *
 * We pick "Introduction to Machine Learning" (slug audio-introduction-to-
 * machine-learning) because it is the clearest "AI" title for a cold visitor,
 * is foundational, and - unlike the old /driver/ sample used by sampleCourses
 * before this change - does NOT depend on the drivers-ed handbook harvest
 * cache that was returning 500 on the Studio page.
 */
// The old slug had no lesson of its own and only played other topics' text.
export const DEMO_COURSE_ID = "audio-intro-to-machine-learning";
export const DEMO_COURSE_TITLE_FALLBACK = "Intro to Machine Learning";

/**
 * Preference order when picking a single demo course from a catalog listing.
 * Used as a fallback when the direct getAudioCourse(DEMO_COURSE_ID) fetch
 * fails for any reason (service down, slug changed, locale missing). Tries:
 *   1. Exact DEMO_COURSE_ID match
 *   2. Any AI / machine-learning / neural / data-science title
 *   3. Any drivers-ed / demo row (the pre-v0.80 behavior)
 *   4. Whatever the catalog returned first
 */
export function sampleCourses<T extends { id: string; title: string; category?: string }>(rows: T[]): T[] {
  if (!rows.length) return rows;
  const byId = rows.find((row) => row.id === DEMO_COURSE_ID);
  if (byId) return [byId];
  const ai = rows.find((row) => /\b(ai|machine[- ]learning|neural|data science|artificial)\b/i
    .test(`${row.id} ${row.title} ${row.category || ""}`));
  if (ai) return [ai];
  const legacy = rows.find((row) => /driver|demo/i
    .test(`${row.id} ${row.title} ${row.category || ""}`));
  return legacy ? [legacy] : rows.slice(0, 1);
}

export function timerLabel(secondsLeft: number): string {
  const s = Math.max(0, Math.floor(secondsLeft));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

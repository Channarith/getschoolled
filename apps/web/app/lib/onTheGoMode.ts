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
};

export function onTheGoExperience(mode: OnTheGoMode): OnTheGoExperience {
  const demo = mode === "demo";
  return {
    mode,
    showTimer: demo,
    sampleSeconds: demo ? ON_THE_GO_DEMO_SECONDS : 0,
    salaAgent: !demo,
    fullCatalog: !demo,
  };
}

export function sampleCourses<T extends { id: string; title: string; category?: string }>(rows: T[]): T[] {
  const sample = rows.filter((row) => /driver|demo/i.test(`${row.id} ${row.title} ${row.category || ""}`));
  const picked = sample.length ? sample : rows;
  return picked.slice(0, 1);
}

export function timerLabel(secondsLeft: number): string {
  const s = Math.max(0, Math.floor(secondsLeft));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

/** The six "how do you learn best" ratings, in the order the setup assistant asks them. */
export const MODES = [
  { id: "video", art: "mode-video", label: "Watching videos", blurb: "Short lessons you can pause and replay." },
  { id: "live_teacher", art: "mode-person", label: "A live teacher", blurb: "Learning in person or in a live class." },
  { id: "presentation", art: "mode-presentation", label: "Presentations", blurb: "Slides and visual walkthroughs." },
  { id: "reading", art: "mode-reading", label: "Reading a book", blurb: "Taking your time with text and notes." },
  { id: "tutoring", art: "mode-tutoring", label: "1:1 tutoring", blurb: "One coach, just for you." },
  { id: "gaming", art: "mode-gaming", label: "Gaming", blurb: "Learning by playing and doing." },
] as const;

/** Previously saved 1–10 ratings for the six modes, ignoring anything else in the saved answers. */
export function savedModalityRatings(answers: Record<string, unknown> | undefined | null): Record<string, number> {
  const raw = answers?.modality_ratings;
  const out: Record<string, number> = {};
  if (!raw || typeof raw !== "object") return out;
  for (const mode of MODES) {
    const value = Number((raw as Record<string, unknown>)[mode.id]);
    if (Number.isInteger(value) && value >= 1 && value <= 10) out[mode.id] = value;
  }
  return out;
}

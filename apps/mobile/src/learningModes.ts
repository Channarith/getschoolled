import type { MascotScene } from "./components/MascotActor";

/**
 * The six learning modalities the setup assistant asks about. Each one now
 * owns a themed mascot scene (`sceneKind`) so the survey page can act out the
 * modality: Sala puts on a baton for "a live teacher", picks up a book for
 * "reading", holds a joystick for "gaming", etc. Keep this list ordered —
 * the one-page-per-choice walker iterates it in order.
 */
export const LEARNING_MODES = [
  { id: "video",        label: "Watching videos", sceneKind: "video" },
  { id: "live_teacher", label: "A live teacher",  sceneKind: "teacher" },
  { id: "presentation", label: "Presentations",   sceneKind: "presentation" },
  { id: "reading",      label: "Reading a book",  sceneKind: "reading" },
  { id: "tutoring",     label: "1:1 tutoring",    sceneKind: "tutoring" },
  { id: "gaming",       label: "Gaming",          sceneKind: "gaming" },
] as const satisfies ReadonlyArray<{
  readonly id: string;
  readonly label: string;
  readonly sceneKind: Extract<MascotScene, { kind: string }>["kind"];
}>;

/** Previously saved 1–10 ratings for the six modalities, ignoring anything else in the saved answers. */
export function savedModalityRatings(answers: Record<string, unknown> | undefined): Record<string, number> {
  const raw = answers?.modality_ratings;
  const out: Record<string, number> = {};
  if (!raw || typeof raw !== "object") return out;
  for (const mode of LEARNING_MODES) {
    const value = Number((raw as Record<string, unknown>)[mode.id]);
    if (Number.isInteger(value) && value >= 1 && value <= 10) out[mode.id] = value;
  }
  return out;
}

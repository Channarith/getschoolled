import type { AssessmentCheckpointSpec } from "./api";

/** Next unfinished formative checkpoint due at or before this slide. */
export function findDueFormativeCheckpoint(
  checkpoints: AssessmentCheckpointSpec[],
  slideIndex: number,
  completedIds: ReadonlySet<string>,
): AssessmentCheckpointSpec | null {
  const due = checkpoints
    .filter((cp) => cp.stage === "formative")
    .filter((cp) => !completedIds.has(cp.checkpoint_id))
    .filter((cp) => slideIndex >= cp.after_slide_index)
    .sort((a, b) => a.after_slide_index - b.after_slide_index);
  return due[0] ?? null;
}

/** End-of-course summative when the learner has reached the final slide. */
export function findDueSummativeCheckpoint(
  checkpoints: AssessmentCheckpointSpec[],
  slideIndex: number,
  completedIds: ReadonlySet<string>,
): AssessmentCheckpointSpec | null {
  const final = checkpoints.find((cp) => cp.stage === "summative");
  if (!final || completedIds.has(final.checkpoint_id)) return null;
  if (slideIndex < final.after_slide_index) return null;
  return final;
}

export function formatLabel(format: string): string {
  switch (format) {
    case "audio":
      return "Audio";
    case "video_aid":
      return "Visual aid";
    case "game":
      return "Challenge";
    default:
      return "Text";
  }
}

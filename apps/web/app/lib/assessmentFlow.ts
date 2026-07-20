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

/** True when advancing onto (or past) the last slide — open the final exam. */
export function shouldOpenSummativeOnAdvance(
  slideIndex: number,
  totalSlides: number,
): boolean {
  if (totalSlides <= 0) return false;
  return slideIndex >= totalSlides - 1;
}

/**
 * Professional / locked courses must not award completion without a verified
 * summative pass (or an exhausted attempt with a recorded decision token).
 */
export function canAwardCourseCompletion(opts: {
  requireVerifiedPass: boolean;
  passDecisionToken: string | null | undefined;
}): boolean {
  if (!opts.requireVerifiedPass) return true;
  if (opts.passDecisionToken) return true;
  // Summative was taken but not passed — still block silent “passed” awards.
  return false;
}

export function isSummativeCompleted(
  checkpoints: AssessmentCheckpointSpec[],
  completedIds: ReadonlySet<string>,
): boolean {
  const final = checkpoints.find((cp) => cp.stage === "summative");
  if (!final) return true;
  return completedIds.has(final.checkpoint_id);
}

export function checkpointTitle(cp: AssessmentCheckpointSpec): string {
  if (cp.title?.trim()) return cp.title.trim();
  if (cp.kind === "final_exam" || cp.stage === "summative") return "End-of-course assessment";
  if (cp.kind === "pop_quiz" || cp.stage === "formative") return "Pop quiz";
  return cp.checkpoint_id;
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

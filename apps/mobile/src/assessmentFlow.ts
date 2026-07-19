/** Helpers for policy checkpoint timing in the mobile lesson UI. */

export type AssessmentCheckpointSpec = {
  checkpoint_id: string;
  stage: "formative" | "summative" | "retention";
  after_slide_index: number;
};

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

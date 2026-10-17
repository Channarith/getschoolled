/** How long a face scan waits for the enrolled student before the lesson or test locks. */
export const FACE_SCAN_LIMIT_MS = 60_000;

export type FaceScanDecision = "match" | "timeout" | "wait";

/**
 * A single miss keeps the scan open. It fails only when the limit passes
 * with no match.
 */
export function decideFaceScan(
  matched: boolean,
  elapsedMs: number,
  limitMs: number = FACE_SCAN_LIMIT_MS,
): FaceScanDecision {
  if (matched) return "match";
  if (elapsedMs >= limitMs) return "timeout";
  return "wait";
}

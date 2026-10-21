/**
 * A failed Learner Check upload that should wait on this computer.
 * Keep this in step with apps/mobile/src/pendingUpload.ts.
 * A pose or audio rejection (422) is not deferred: that capture cannot be sent later.
 */

const REJECTED = /pose challenge|does not match|too quiet|silent|clipped|too short|between 8 and 15|decoded/i;

export function uploadStatus(reason: unknown): number | null {
  const tagged = (reason as { status?: number } | null)?.status;
  if (typeof tagged === "number" && tagged >= 100 && tagged <= 599) return tagged;
  const message = String((reason as Error)?.message ?? reason ?? "");
  const match = message.match(/^(\d{3})\b/);
  if (!match) return null;
  const code = Number(match[1]);
  return code >= 400 && code <= 599 ? code : null;
}

export function isDeferredUpload(reason: unknown): boolean {
  const message = String((reason as Error)?.message ?? reason ?? "");
  if (REJECTED.test(message)) return false;
  const status = uploadStatus(reason);
  if (status == null) {
    return /failed to fetch|network request failed|network|timeout|timed out|taking too long|aborted|offline|load failed|typeerror/i.test(message);
  }
  if (status === 408 || status === 429) return true;
  return status >= 500;
}

/** The server looked at the capture and refused it. Do not retry that payload. */
export function isRejectedCapture(reason: unknown): boolean {
  if (isDeferredUpload(reason)) return false;
  const status = uploadStatus(reason);
  if (status === 400 || status === 413 || status === 422) return true;
  return REJECTED.test(String((reason as Error)?.message ?? reason ?? ""));
}

/**
 * The signed-in account does not own this learner. On a shared device the
 * capture belongs to someone else, so it waits for that account instead of
 * being thrown away.
 */
export function isForeignLearner(reason: unknown): boolean {
  const status = uploadStatus(reason);
  if (status === 401 || status === 403 || status === 404) return true;
  return /student not found|unknown student|not signed in|sign in again/i.test(
    String((reason as Error)?.message ?? reason ?? ""),
  );
}

export const PENDING_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;

/** 15s, 30s, 1m ... capped at 15 minutes, so a struggling service is not hammered. */
export function pendingRetryDelayMs(attempts: number): number {
  const step = Math.max(0, Math.min(Math.floor(attempts), 6));
  return Math.min(15 * 60 * 1000, 15_000 * 2 ** step);
}

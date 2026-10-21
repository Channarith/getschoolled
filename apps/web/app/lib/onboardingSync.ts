"use client";

/**
 * Small, bounded outbox for the two final onboarding writes.
 *
 * A plan selection or completion can be accepted by identity just before an
 * ingress 504 reaches the browser. Retrying immediately can amplify a
 * degraded service, so keep one idempotent free-plan job locally and retry
 * only after a capped exponential delay or the browser's next online event.
 */
import {
  completeOnboarding,
  getToken,
  selectOnboardingPlan,
  submitLearningProfile,
} from "./api";

const KEY = "aoep_pending_onboarding_sync_v1";
const MAX_BACKOFF_STEP = 6;
const MAX_DELAY_MS = 15 * 60_000;

type PendingOnboarding = {
  tokenTail: string;
  plan?: "free";
  profile?: { studentId: string; answers: Record<string, unknown> };
  complete?: { learner_name?: string; age_band?: string };
  attempts: number;
  retryAt: number;
};

let flushing: Promise<boolean> | null = null;

function tokenTail(): string {
  return getToken()?.slice(-24) || "";
}

function load(): PendingOnboarding | null {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "") as PendingOnboarding;
    if (!parsed || !tokenTail() || parsed.tokenTail !== tokenTail()) return null;
    if (!parsed.complete && !parsed.profile && !parsed.plan) return null;
    return parsed;
  } catch {
    return null;
  }
}

function save(value: PendingOnboarding): void {
  localStorage.setItem(KEY, JSON.stringify(value));
}

function clear(): void {
  localStorage.removeItem(KEY);
}

function retryDelay(attempts: number): number {
  return Math.min(MAX_DELAY_MS, 15_000 * (2 ** Math.min(attempts, 6)));
}

/** How long a final onboarding save may hold the learner before it moves to the outbox. */
export const SAVE_WAIT_MS = 5000;

/** Reject when a save does not settle in time. The request itself keeps running. */
export function waitFor<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(message)), ms);
    promise.then(
      (value) => { clearTimeout(timer); resolve(value); },
      (reason) => { clearTimeout(timer); reject(reason); },
    );
  });
}

export function isRetryableIdentityWrite(reason: unknown): boolean {
  const message = String((reason as Error)?.message ?? reason ?? "");
  const status = Number(message.match(/\b(502|503|504|408|429)\b/)?.[1]);
  return Boolean(status)
    || /failed to fetch|networkerror|network request failed|load failed|timed out|timeout/i.test(message);
}

/** True once the learner finished onboarding here and identity has not caught up. */
export function hasPendingOnboardingSync(): boolean {
  return Boolean(load()?.complete);
}

/** Keep the 1–10 ratings when identity cannot take them, so the learner can go on. */
export function queueLearningProfileSync(studentId: string, answers: Record<string, unknown>): void {
  const existing = load();
  save({
    ...(existing ?? { attempts: 0 }),
    tokenTail: tokenTail(),
    profile: { studentId, answers },
    retryAt: Date.now() + 15_000,
  });
}

export function queueOnboardingSync(
  complete: PendingOnboarding["complete"],
  plan?: "free",
): void {
  const existing = load();
  save({
    tokenTail: tokenTail(),
    plan: plan ?? existing?.plan,
    profile: existing?.profile,
    complete,
    attempts: existing?.attempts ?? 0,
    retryAt: Date.now() + 15_000,
  });
}

/** Retry one queued finish at most once when the browser becomes available. */
export async function flushPendingOnboardingSync(force = false): Promise<boolean> {
  if (flushing) return flushing;
  const pending = load();
  if (!pending || (!force && pending.retryAt > Date.now())) return false;
  flushing = (async () => {
    try {
      if (pending.profile) {
        try {
          await submitLearningProfile(pending.profile.studentId, pending.profile.answers);
        } catch (reason) {
          // Ratings identity refuses are optional; the finish behind them is not.
          if (isRetryableIdentityWrite(reason)) throw reason;
        }
        pending.profile = undefined;
        save(pending);
      }
      if (pending.plan) {
        await selectOnboardingPlan(pending.plan);
        pending.plan = undefined;
        save(pending);
      }
      if (pending.complete) await completeOnboarding(pending.complete);
      clear();
      return true;
    } catch (reason) {
      if (!isRetryableIdentityWrite(reason)) {
        // A validated client/auth failure should be shown on the next visit;
        // never hammer identity with a job it will reject.
        clear();
        return false;
      }
      // Keep the one idempotent write, but after six failures retry only at
      // the 15-minute ceiling. This recovers from a longer identity outage
      // without turning every open browser into a retry storm.
      const attempts = Math.min(MAX_BACKOFF_STEP, pending.attempts + 1);
      save({ ...pending, attempts, retryAt: Date.now() + retryDelay(attempts) });
      return false;
    } finally {
      flushing = null;
    }
  })();
  return flushing;
}

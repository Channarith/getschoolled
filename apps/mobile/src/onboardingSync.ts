/**
 * Small, bounded outbox for the two final onboarding writes.
 * Keep this in step with apps/web/app/lib/onboardingSync.ts.
 *
 * Identity can accept the free plan or completion just before the gateway
 * returns 504. The learner moves on, and one idempotent job is retried after
 * a capped delay or the next time the app comes to the foreground.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

import { completeMobileAccountOnboarding, selectMobileOnboardingPlan, submitLearningProfile } from "./api";
import { getToken } from "./storage";

const KEY = "aoep_pending_onboarding_sync_v1";
const MAX_BACKOFF_STEP = 6;
const MAX_DELAY_MS = 15 * 60_000;

type PendingOnboarding = {
  tokenTail: string;
  plan?: "free";
  profile?: { studentId: string; answers: Record<string, unknown> };
  complete?: { learnerName: string; ageBand: string };
  attempts: number;
  retryAt: number;
};

let flushing: Promise<boolean> | null = null;

function tokenTail(): string {
  return getToken()?.slice(-24) || "";
}

async function load(): Promise<PendingOnboarding | null> {
  try {
    const parsed = JSON.parse((await AsyncStorage.getItem(KEY)) || "") as PendingOnboarding;
    if (!parsed || !tokenTail() || parsed.tokenTail !== tokenTail()) return null;
    if (!parsed.complete && !parsed.profile && !parsed.plan) return null;
    return parsed;
  } catch {
    return null;
  }
}

async function save(value: PendingOnboarding): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(value));
}

async function clear(): Promise<void> {
  await AsyncStorage.removeItem(KEY).catch(() => undefined);
}

function retryDelay(attempts: number): number {
  return Math.min(MAX_DELAY_MS, 15_000 * (2 ** Math.min(attempts, MAX_BACKOFF_STEP)));
}

export function isRetryableIdentityWrite(reason: unknown): boolean {
  const tagged = (reason as { status?: number } | null)?.status;
  if (typeof tagged === "number") {
    return tagged === 408 || tagged === 429 || tagged === 502 || tagged === 503 || tagged === 504;
  }
  const message = String((reason as Error)?.message ?? reason ?? "");
  return /\b(502|503|504|408|429)\b/.test(message)
    || /network request failed|failed to fetch|aborted|timed out|timeout/i.test(message);
}

/** True once the learner finished onboarding here and identity has not caught up. */
export async function hasPendingOnboardingSync(): Promise<boolean> {
  return Boolean((await load())?.complete);
}

/** Keep the 1–10 ratings when identity cannot take them, so the learner can go on. */
export async function queueLearningProfileSync(
  studentId: string,
  answers: Record<string, unknown>,
): Promise<void> {
  const existing = await load();
  await save({
    ...(existing ?? { attempts: 0 }),
    tokenTail: tokenTail(),
    profile: { studentId, answers },
    retryAt: Date.now() + 15_000,
  });
}

export async function queueOnboardingSync(
  learnerName: string,
  ageBand: string,
  plan?: "free",
): Promise<void> {
  const existing = await load();
  await save({
    tokenTail: tokenTail(),
    plan: plan ?? existing?.plan,
    profile: existing?.profile,
    complete: { learnerName, ageBand },
    attempts: existing?.attempts ?? 0,
    retryAt: Date.now() + 15_000,
  });
}

/** Retry the queued finish once its wait has passed (or now, with `force`). */
export function flushPendingOnboardingSync(force = false): Promise<boolean> {
  if (flushing) return flushing;
  flushing = (async () => {
    const pending = await load();
    if (!pending || (!force && pending.retryAt > Date.now())) return false;
    try {
      if (pending.profile) {
        try {
          await submitLearningProfile(pending.profile.studentId, pending.profile.answers);
        } catch (reason) {
          // Ratings identity refuses are optional; the finish behind them is not.
          if (isRetryableIdentityWrite(reason)) throw reason;
        }
        pending.profile = undefined;
        await save(pending);
      }
      if (pending.plan) {
        await selectMobileOnboardingPlan(pending.plan);
        pending.plan = undefined;
        await save(pending);
      }
      if (pending.complete) {
        await completeMobileAccountOnboarding(pending.complete.learnerName, pending.complete.ageBand);
      }
      await clear();
      return true;
    } catch (reason) {
      if (!isRetryableIdentityWrite(reason)) {
        // Identity refused the job. Retrying it would only add load; the
        // onboarding gate shows the step again on the next sign-in.
        await clear();
        return false;
      }
      const attempts = Math.min(MAX_BACKOFF_STEP, pending.attempts + 1);
      await save({ ...pending, attempts, retryAt: Date.now() + retryDelay(attempts) });
      return false;
    }
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}

/**
 * Optional Sentry wiring — safe to call even when @sentry/react-native is not
 * installed and no DSN is configured. In that case every function is a no-op.
 *
 * To activate off-device crash reporting without any code change:
 *   1. `cd apps/mobile && pnpm add @sentry/react-native`
 *   2. Export SENTRY_DSN in your shell before building (or set extra.sentryDsn
 *      in app.config.js). Expo exposes it to the running app via Constants.
 *   3. Cut a fresh native release build (Gradle / Xcode — see
 *      .cursor/rules/no-eas-build-mobile.mdc). Native modules only link in a
 *      native build; a JS-only re-export won't pick up the SDK.
 *
 * All imports are dynamic so a missing package / failing init never breaks
 * client logging or the error handler — crashes still land in the durable
 * on-device crash file (src/crashLog.ts) regardless.
 */

import Constants from "expo-constants";

type SentryLike = {
  init(opts: { dsn: string; enableAutoSessionTracking?: boolean; release?: string }): void;
  captureException(err: unknown, hint?: Record<string, unknown>): void;
  addBreadcrumb?(bc: { category?: string; message?: string; level?: string }): void;
  wrap?<T>(component: T): T;
};

let sentry: SentryLike | null = null;
let initialised = false;

function dsnFromEnv(): string | null {
  const extra = (Constants.expoConfig?.extra || {}) as Record<string, string | undefined>;
  const fromExtra = extra.sentryDsn;
  // process.env is injected by babel-plugin-transform-inline-environment-variables
  // at bundle time; mobile tsconfig has no @types/node so read it structurally.
  const proc = (globalThis as unknown as {
    process?: { env?: Record<string, string | undefined> };
  }).process;
  const fromProcess = proc?.env?.SENTRY_DSN;
  const dsn = (fromExtra || fromProcess || "").trim();
  return dsn || null;
}

function tryLoad(): SentryLike | null {
  if (sentry) return sentry;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require("@sentry/react-native");
    sentry = (mod?.default || mod) as SentryLike;
    return sentry;
  } catch {
    return null;
  }
}

/**
 * Call once from index.ts (or App). Idempotent and never throws.
 * Returns true if Sentry was initialised, false otherwise (missing dep or
 * DSN). When false, captureFatal() is a no-op — the on-device crash file
 * still works.
 */
export function initSentry(release?: string): boolean {
  if (initialised) return !!sentry;
  initialised = true;
  const dsn = dsnFromEnv();
  if (!dsn) return false;
  const impl = tryLoad();
  if (!impl?.init) return false;
  try {
    impl.init({
      dsn,
      enableAutoSessionTracking: true,
      release,
    });
    return true;
  } catch {
    sentry = null;
    return false;
  }
}

export function captureFatal(err: unknown, hint?: { isFatal?: boolean }): void {
  if (!sentry) return;
  try {
    sentry.captureException(err, { level: hint?.isFatal ? "fatal" : "error" });
  } catch { /* best-effort */ }
}

export function addBreadcrumb(category: string, message: string): void {
  if (!sentry) return;
  try {
    sentry.addBreadcrumb?.({ category, message, level: "info" });
  } catch { /* best-effort */ }
}

/** Ring buffer of recent client log lines for bug reports (React Native).
 *
 * Besides the in-memory ring, this module now also:
 *   • captures unhandled promise rejections (Hermes + fallback)
 *   • wraps RN's global ErrorUtils handler so fatal JS errors are recorded
 *   • mirrors the ring to AsyncStorage every ~2 s (debounced) so a crash
 *     restores the breadcrumbs on next launch
 *   • writes a durable crash record via src/crashLog.ts for the Bug Reporter
 *   • opportunistically calls into Sentry when it's installed and DSN-wired
 *     (see src/sentryHook.ts). All of this is best-effort: a failing dep
 *     never breaks client logging itself.
 */

import { writeCrashRecord } from "./crashLog";

const MAX_LINES = 120;
const PERSIST_KEY = "@salareen/client-log-buffer";
const PERSIST_DEBOUNCE_MS = 2000;

let installed = false;
const buffer: string[] = [];

type ErrorHandler = (err: Error, isFatal?: boolean) => void;

type ErrorUtilsHost = {
  ErrorUtils?: {
    setGlobalHandler?: (fn: ErrorHandler) => void;
    getGlobalHandler?: () => ErrorHandler | undefined;
  };
};

type FetchHost = typeof globalThis & {
  fetch?: typeof fetch;
};

// Dynamic require: AsyncStorage must exist in RN runtimes but may be absent in
// jest or SSR. We don't want a missing import to break the error handler.
type AsyncStorageLike = {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
};
function tryAsyncStorage(): AsyncStorageLike | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require("@react-native-async-storage/async-storage");
    return (mod?.default || mod) as AsyncStorageLike;
  } catch {
    return null;
  }
}
const storage = tryAsyncStorage();

function push(line: string) {
  const s = line.trim();
  if (!s) return;
  buffer.push(`${new Date().toISOString()} ${s}`);
  if (buffer.length > MAX_LINES) buffer.splice(0, buffer.length - MAX_LINES);
  schedulePersist();
}

let persistTimer: ReturnType<typeof setTimeout> | null = null;
function schedulePersist() {
  if (!storage || persistTimer) return;
  persistTimer = setTimeout(() => {
    persistTimer = null;
    void storage.setItem(PERSIST_KEY, JSON.stringify(buffer)).catch(() => {});
  }, PERSIST_DEBOUNCE_MS);
}

function safeRequestLabel(input: Parameters<typeof fetch>[0]): string {
  const raw = typeof input === "string" ? input
    : input instanceof URL ? input.href
    : input.url;
  try {
    const parsed = new URL(raw);
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return raw.split("?")[0]?.slice(0, 300) || "[request]";
  }
}

/**
 * Install all client-side instrumentation. Idempotent and safe to call
 * multiple times. Call this as EARLY as possible — from index.ts, BEFORE
 * registerRootComponent(App) runs — so a throw during any Provider's mount
 * is captured even though it happens before App's own useEffect fires.
 */
export function installClientLog(): void {
  if (installed) return;
  installed = true;

  // Restore the previous session's breadcrumbs (if any) so a crash's log
  // tail survives into the Bug Reporter on next launch.
  if (storage) {
    void storage
      .getItem(PERSIST_KEY)
      .then((raw) => {
        if (!raw) return;
        try {
          const prev = JSON.parse(raw);
          if (Array.isArray(prev)) {
            // Prepend as "[prev] …" and cap to MAX_LINES.
            const marked = (prev as unknown[]).map((l) => `[prev] ${String(l)}`);
            buffer.splice(0, 0, ...marked.slice(-MAX_LINES));
            if (buffer.length > MAX_LINES) buffer.splice(0, buffer.length - MAX_LINES);
          }
        } catch { /* ignore malformed */ }
      })
      .catch(() => {});
  }

  const origError = console.error.bind(console);
  const origWarn = console.warn.bind(console);
  console.error = (...args: unknown[]) => {
    push(`error: ${args.map(String).join(" ")}`);
    origError(...args);
  };
  console.warn = (...args: unknown[]) => {
    push(`warn: ${args.map(String).join(" ")}`);
    origWarn(...args);
  };

  // React Native global error handler. Wrapping it lets us record the
  // crash to disk BEFORE calling the previous handler (which, for a fatal
  // JS error, will call native ExceptionsManager.reportException → abort()).
  const g = globalThis as typeof globalThis & ErrorUtilsHost;
  const eu = g.ErrorUtils;
  if (eu?.setGlobalHandler) {
    const prev = eu.getGlobalHandler?.();
    eu.setGlobalHandler((err: Error, isFatal?: boolean) => {
      try {
        push(`fatal=${Boolean(isFatal)}: ${err?.stack || err?.message || String(err)}`);
        writeCrashRecord({ error: err, isFatal: Boolean(isFatal), source: "errorUtils" });
        void storage?.setItem(PERSIST_KEY, JSON.stringify(buffer)).catch(() => {});
        // Opportunistic Sentry report (no-op if Sentry isn't installed/activated).
        try {
          // eslint-disable-next-line @typescript-eslint/no-var-requires
          const sentryHook = require("./sentryHook");
          sentryHook?.captureFatal?.(err, { isFatal: Boolean(isFatal) });
        } catch { /* sentryHook missing or not initialized */ }
      } catch { /* never let the error handler itself throw */ }
      prev?.(err, isFatal);
    });
  }

  // Unhandled promise rejections (Hermes-first, with fallback). RN sets up
  // promise rejection tracking out of the box in RN >= 0.70; we hook its
  // onUnhandled callback so the breadcrumb + crash record are populated.
  installUnhandledRejectionHook();

  // Record API status/latency without bodies, headers, tokens, or query strings.
  const host = globalThis as FetchHost;
  const originalFetch = host.fetch?.bind(globalThis);
  if (originalFetch) {
    host.fetch = async (input: Parameters<typeof fetch>[0], init?: RequestInit) => {
      const started = Date.now();
      const method = (init?.method || (typeof Request !== "undefined" && input instanceof Request
        ? input.method : "GET")).toUpperCase();
      const label = safeRequestLabel(input);
      try {
        const response = await originalFetch(input as RequestInfo, init);
        push(`api ${method} ${label} -> ${response.status} ${Date.now() - started}ms`);
        return response;
      } catch (error) {
        push(`api ${method} ${label} -> network-error ${Date.now() - started}ms: ${String(error)}`);
        throw error;
      }
    };
  }
}

function installUnhandledRejectionHook() {
  // RN's bundled promise polyfill (`promise/setimmediate/rejection-tracking`)
  // is enabled by react-native's init. We enable it with our callback so we
  // see the reason object. Dynamic require because the path can shift between
  // RN minor versions and we never want to crash install if it's absent.
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const tracking = require("promise/setimmediate/rejection-tracking");
    tracking.enable({
      allRejections: true,
      onUnhandled: (_id: number, rejection: unknown) => {
        const err = toError(rejection);
        push(`unhandledRejection: ${err.message}`);
        writeCrashRecord({ error: err, isFatal: false, source: "unhandledRejection" });
        try {
          // eslint-disable-next-line @typescript-eslint/no-var-requires
          require("./sentryHook")?.captureFatal?.(err, { isFatal: false });
        } catch { /* ignore */ }
      },
      onHandled: () => { /* no-op */ },
    });
  } catch {
    // Fallback: the `unhandledrejection` event may be dispatched by Hermes.
    const g = globalThis as unknown as {
      addEventListener?: (type: string, cb: (ev: { reason?: unknown }) => void) => void;
    };
    g.addEventListener?.("unhandledrejection", (ev) => {
      const err = toError(ev?.reason);
      push(`unhandledRejection: ${err.message}`);
      writeCrashRecord({ error: err, isFatal: false, source: "unhandledRejection" });
    });
  }
}

function toError(x: unknown): Error {
  if (x instanceof Error) return x;
  if (typeof x === "string") return new Error(x);
  try { return new Error(JSON.stringify(x)); } catch { return new Error(String(x)); }
}

export function drainClientLogs(): string[] {
  const logs = [...buffer];
  buffer.length = 0;
  if (storage) void storage.removeItem(PERSIST_KEY).catch(() => {});
  return logs;
}

/** Snapshot without draining (for the Bug Reporter preview). */
export function peekClientLogs(): string[] {
  return [...buffer];
}

/** Ring buffer of recent client log lines for bug reports (React Native). */

const MAX_LINES = 120;

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

function push(line: string) {
  const s = line.trim();
  if (!s) return;
  buffer.push(s);
  if (buffer.length > MAX_LINES) buffer.splice(0, buffer.length - MAX_LINES);
}

function safeRequestLabel(input: RequestInfo): string {
  const raw = typeof input === "string" ? input : input.url;
  try {
    const parsed = new URL(raw);
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return raw.split("?")[0]?.slice(0, 300) || "[request]";
  }
}

export function installClientLog(): void {
  if (installed) return;
  installed = true;

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

  // React Native global error handler (if present).
  const g = globalThis as typeof globalThis & ErrorUtilsHost;
  const eu = g.ErrorUtils;
  if (eu?.setGlobalHandler) {
    const prev = eu.getGlobalHandler?.();
    eu.setGlobalHandler((err: Error, isFatal?: boolean) => {
      push(`fatal=${Boolean(isFatal)}: ${err?.stack || err?.message || String(err)}`);
      prev?.(err, isFatal);
    });
  }

  // Record API status/latency without bodies, headers, tokens, or query strings.
  const host = globalThis as FetchHost;
  const originalFetch = host.fetch?.bind(globalThis);
  if (originalFetch) {
    host.fetch = async (input: RequestInfo, init?: RequestInit) => {
      const started = Date.now();
      const method = (init?.method || (typeof Request !== "undefined" && input instanceof Request
        ? input.method : "GET")).toUpperCase();
      const label = safeRequestLabel(input);
      try {
        const response = await originalFetch(input, init);
        push(`api ${method} ${label} -> ${response.status} ${Date.now() - started}ms`);
        return response;
      } catch (error) {
        push(`api ${method} ${label} -> network-error ${Date.now() - started}ms: ${String(error)}`);
        throw error;
      }
    };
  }
}

export function drainClientLogs(): string[] {
  const logs = [...buffer];
  buffer.length = 0;
  return logs;
}

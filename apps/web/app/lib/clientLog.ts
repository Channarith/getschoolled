/** Ring buffer of recent client log lines for bug reports. */

const MAX_LINES = 120;

let installed = false;
const buffer: string[] = [];

function push(line: string) {
  const s = line.trim();
  if (!s) return;
  buffer.push(s);
  if (buffer.length > MAX_LINES) buffer.splice(0, buffer.length - MAX_LINES);
}

function safeRequestLabel(input: RequestInfo | URL): string {
  try {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(raw, window.location.origin);
    return `${url.origin === window.location.origin ? "" : url.origin}${url.pathname}`;
  } catch {
    return "[request]";
  }
}

export function installClientLog(): void {
  if (installed || typeof window === "undefined") return;
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

  window.addEventListener("error", (ev) => {
    const msg = ev.message || "window error";
    const loc = ev.filename ? ` @ ${ev.filename}:${ev.lineno}` : "";
    push(`window: ${msg}${loc}`);
  });
  window.addEventListener("unhandledrejection", (ev) => {
    const reason = ev.reason as Error | undefined;
    push(`promise: ${String(reason?.stack || reason?.message || ev.reason)}`);
  });

  // Keep a compact API breadcrumb trail. Never record request/response bodies,
  // auth headers, or query strings: diagnostics should help without leaking data.
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const started = performance.now();
    const method = (init?.method || (input instanceof Request ? input.method : "GET")).toUpperCase();
    const label = safeRequestLabel(input);
    try {
      const response = await originalFetch(input, init);
      push(`api ${method} ${label} -> ${response.status} ${Math.round(performance.now() - started)}ms`);
      return response;
    } catch (error) {
      push(`api ${method} ${label} -> network-error ${Math.round(performance.now() - started)}ms: ${String(error)}`);
      throw error;
    }
  };
}

export function drainClientLogs(): string[] {
  const logs = [...buffer];
  buffer.length = 0;
  return logs;
}

export function peekClientLogs(): string[] {
  return [...buffer];
}

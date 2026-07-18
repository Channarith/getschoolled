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
    push(`promise: ${String((ev.reason as Error)?.message || ev.reason)}`);
  });
}

export function drainClientLogs(): string[] {
  return [...buffer];
}

export function peekClientLogs(): string[] {
  return [...buffer];
}

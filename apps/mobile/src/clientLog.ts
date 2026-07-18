/** Ring buffer of recent client log lines for bug reports (React Native). */

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
  const g = global as typeof global & {
    ErrorUtils?: { setGlobalHandler?: (fn: (err: Error, isFatal?: boolean) => void) => void };
  };
  const eu = g.ErrorUtils;
  if (eu?.setGlobalHandler) {
    const prev = (eu as { getGlobalHandler?: () => (err: Error, isFatal?: boolean) => void })
      .getGlobalHandler?.();
    eu.setGlobalHandler((err, isFatal) => {
      push(`fatal=${Boolean(isFatal)}: ${err?.message || String(err)}`);
      prev?.(err, isFatal);
    });
  }
}

export function drainClientLogs(): string[] {
  return [...buffer];
}

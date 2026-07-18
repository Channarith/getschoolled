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
  const g = globalThis as typeof globalThis & ErrorUtilsHost;
  const eu = g.ErrorUtils;
  if (eu?.setGlobalHandler) {
    const prev = eu.getGlobalHandler?.();
    eu.setGlobalHandler((err: Error, isFatal?: boolean) => {
      push(`fatal=${Boolean(isFatal)}: ${err?.message || String(err)}`);
      prev?.(err, isFatal);
    });
  }
}

export function drainClientLogs(): string[] {
  return [...buffer];
}

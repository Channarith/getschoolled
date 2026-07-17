import { ensureDOMExceptionGlobal } from "./domException";
import { ensureTextEncodingGlobals } from "./textEncoding";

/** Install Hermes-safe globals required before any LiveKit module evaluates. */
export function ensureLiveKitGlobals(): void {
  ensureTextEncodingGlobals();
  ensureDOMExceptionGlobal();
}

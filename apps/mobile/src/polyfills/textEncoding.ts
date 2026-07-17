/**
 * Hermes (React Native) does not expose TextEncoder/TextDecoder globally.
 * livekit-client reads them at module-evaluation time, before
 * `@livekit/react-native`'s registerGlobals() can run — so lazy LiveKit loads
 * must install this polyfill first.
 */
type TextEncodingHost = typeof globalThis & {
  TextDecoder?: unknown;
  TextEncoder?: unknown;
};

export function ensureTextEncodingGlobals(): void {
  const host = globalThis as TextEncodingHost;
  if (typeof host.TextDecoder !== "undefined") return;
  // Side-effect module: patches global TextEncoder/TextDecoder (utf-8 only).
  require("fast-text-encoding");
}

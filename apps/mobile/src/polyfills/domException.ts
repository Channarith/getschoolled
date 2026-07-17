/**
 * Hermes lacks DOMException. livekit-client's bundled webrtc-adapter throws it
 * during connect/publish on both iOS and Android once WebRTC paths execute.
 */
type DOMExceptionCtor = new (message?: string, name?: string) => Error;
type DOMExceptionHost = typeof globalThis & {
  DOMException?: DOMExceptionCtor;
};

export function ensureDOMExceptionGlobal(): void {
  const host = globalThis as DOMExceptionHost;
  if (typeof host.DOMException !== "undefined") return;

  class DOMExceptionPolyfill extends Error {
    constructor(message = "", name = "Error") {
      super(message);
      this.name = name;
    }
  }

  host.DOMException = DOMExceptionPolyfill;
}

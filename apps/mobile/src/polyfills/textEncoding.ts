/**
 * Hermes (React Native) does not expose TextEncoder/TextDecoder globally.
 * livekit-client reads them at module-evaluation time, before
 * `@livekit/react-native`'s registerGlobals() can run — so lazy LiveKit loads
 * must install this polyfill first.
 *
 * Inlined utf-8 codec (no npm dep) so Metro/Xcode release bundles always resolve
 * it — fast-text-encoding was missing from some pnpm hoists during archive.
 */
type TextEncodingHost = typeof globalThis & {
  TextDecoder?: new (
    label?: string,
    options?: { fatal?: boolean; ignoreBOM?: boolean },
  ) => { decode(input?: ArrayBuffer | ArrayBufferView): string };
  TextEncoder?: new () => { encode(input?: string): Uint8Array };
};

function utf8Encode(input: string): Uint8Array {
  const out: number[] = [];
  for (let i = 0; i < input.length; i += 1) {
    let code = input.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff && i + 1 < input.length) {
      const next = input.charCodeAt(i + 1);
      if (next >= 0xdc00 && next <= 0xdfff) {
        code = 0x10000 + ((code - 0xd800) << 10) + (next - 0xdc00);
        i += 1;
      }
    }
    if (code < 0x80) {
      out.push(code);
    } else if (code < 0x800) {
      out.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
    } else if (code < 0x10000) {
      out.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
    } else {
      out.push(
        0xf0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3f),
        0x80 | ((code >> 6) & 0x3f),
        0x80 | (code & 0x3f),
      );
    }
  }
  return Uint8Array.from(out);
}

function utf8Decode(bytes: Uint8Array): string {
  let out = "";
  for (let i = 0; i < bytes.length; i += 1) {
    const b0 = bytes[i];
    if (b0 < 0x80) {
      out += String.fromCharCode(b0);
    } else if ((b0 & 0xe0) === 0xc0 && i + 1 < bytes.length) {
      const b1 = bytes[i + 1];
      out += String.fromCharCode(((b0 & 0x1f) << 6) | (b1 & 0x3f));
      i += 1;
    } else if ((b0 & 0xf0) === 0xe0 && i + 2 < bytes.length) {
      const b1 = bytes[i + 1];
      const b2 = bytes[i + 2];
      out += String.fromCharCode(((b0 & 0x0f) << 12) | ((b1 & 0x3f) << 6) | (b2 & 0x3f));
      i += 2;
    } else if ((b0 & 0xf8) === 0xf0 && i + 3 < bytes.length) {
      const b1 = bytes[i + 1];
      const b2 = bytes[i + 2];
      const b3 = bytes[i + 3];
      const code =
        ((b0 & 0x07) << 18)
        | ((b1 & 0x3f) << 12)
        | ((b2 & 0x3f) << 6)
        | (b3 & 0x3f);
      const offset = code - 0x10000;
      out += String.fromCharCode(0xd800 + (offset >> 10), 0xdc00 + (offset & 0x3ff));
      i += 3;
    }
  }
  return out;
}

class TextEncoderPolyfill {
  readonly encoding = "utf-8";

  encode(input = ""): Uint8Array {
    return utf8Encode(String(input));
  }
}

class TextDecoderPolyfill {
  readonly encoding = "utf-8";
  readonly fatal = false;
  readonly ignoreBOM = false;

  constructor(_label?: string, _options?: { fatal?: boolean; ignoreBOM?: boolean }) {
    /* utf-8 only — matches livekit-client usage on Hermes */
  }

  decode(input?: ArrayBuffer | ArrayBufferView, _options?: { stream?: boolean }): string {
    if (input == null) return "";
    const bytes =
      input instanceof Uint8Array
        ? input
        : input instanceof ArrayBuffer
          ? new Uint8Array(input)
          : new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
    return utf8Decode(bytes);
  }
}

export function ensureTextEncodingGlobals(): void {
  const host = globalThis as TextEncodingHost;
  if (typeof host.TextDecoder !== "undefined") return;
  host.TextEncoder = TextEncoderPolyfill as TextEncodingHost["TextEncoder"];
  host.TextDecoder = TextDecoderPolyfill as TextEncodingHost["TextDecoder"];
}

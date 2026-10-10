/** PCM16 LE audio helpers for the xAI Grok voice stream (24 kHz mono). */

function writeAscii(out: Uint8Array, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) out[offset + i] = text.charCodeAt(i);
}

function writeU32(out: Uint8Array, offset: number, value: number): void {
  out[offset] = value & 0xff;
  out[offset + 1] = (value >> 8) & 0xff;
  out[offset + 2] = (value >> 16) & 0xff;
  out[offset + 3] = (value >> 24) & 0xff;
}

function writeU16(out: Uint8Array, offset: number, value: number): void {
  out[offset] = value & 0xff;
  out[offset + 1] = (value >> 8) & 0xff;
}

export function pcm16ToWav(pcm: Uint8Array, sampleRate = 24000): Uint8Array {
  const dataBytes = pcm.length - (pcm.length % 2);
  const out = new Uint8Array(44 + dataBytes);
  writeAscii(out, 0, "RIFF");
  writeU32(out, 4, 36 + dataBytes);
  writeAscii(out, 8, "WAVE");
  writeAscii(out, 12, "fmt ");
  writeU32(out, 16, 16);
  writeU16(out, 20, 1);
  writeU16(out, 22, 1);
  writeU32(out, 24, sampleRate);
  writeU32(out, 28, sampleRate * 2);
  writeU16(out, 32, 2);
  writeU16(out, 34, 16);
  writeAscii(out, 36, "data");
  writeU32(out, 40, dataBytes);
  out.set(pcm.subarray(0, dataBytes), 44);
  return out;
}

const B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

export function encodeBase64(bytes: Uint8Array): string {
  let out = "";
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i];
    const b = i + 1 < bytes.length ? bytes[i + 1] : 0;
    const c = i + 2 < bytes.length ? bytes[i + 2] : 0;
    const triple = (a << 16) | (b << 8) | c;
    out += B64[(triple >> 18) & 63];
    out += B64[(triple >> 12) & 63];
    out += i + 1 < bytes.length ? B64[(triple >> 6) & 63] : "=";
    out += i + 2 < bytes.length ? B64[triple & 63] : "=";
  }
  return out;
}

export function decodeBase64(value: string): Uint8Array {
  const clean = value.replace(/[^A-Za-z0-9+/]/g, "");
  const len = clean.length;
  const bytes: number[] = [];
  for (let i = 0; i < len; i += 4) {
    const a = B64.indexOf(clean[i] || "A");
    const b = B64.indexOf(clean[i + 1] || "A");
    const c = B64.indexOf(clean[i + 2] || "A");
    const d = B64.indexOf(clean[i + 3] || "A");
    const triple = (a << 18) | (b << 12) | (c << 6) | d;
    bytes.push((triple >> 16) & 255);
    if (i + 2 < len) bytes.push((triple >> 8) & 255);
    if (i + 3 < len) bytes.push(triple & 255);
  }
  return Uint8Array.from(bytes);
}

export function concatBytes(parts: Uint8Array[]): Uint8Array {
  const size = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

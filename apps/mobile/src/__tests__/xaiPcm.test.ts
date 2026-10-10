import { decodeBase64, encodeBase64, pcm16ToWav } from "../xaiPcm";

describe("xai pcm wav", () => {
  it("wraps pcm16 as a mono wav other players can open", () => {
    const pcm = Uint8Array.from([1, 2, 3, 4]);
    const wav = pcm16ToWav(pcm, 24000);
    expect(wav.length).toBe(48);
    expect(String.fromCharCode(...wav.subarray(0, 4))).toBe("RIFF");
    expect(String.fromCharCode(...wav.subarray(8, 12))).toBe("WAVE");
    expect(wav[44]).toBe(1);
    expect(wav[47]).toBe(4);
  });

  it("round-trips base64", () => {
    const bytes = Uint8Array.from([0, 1, 2, 250, 255]);
    expect(Array.from(decodeBase64(encodeBase64(bytes)))).toEqual(Array.from(bytes));
  });
});

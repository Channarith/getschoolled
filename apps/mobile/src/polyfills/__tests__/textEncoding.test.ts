/** @jest-environment node */

type TextEncodingHost = typeof globalThis & {
  TextDecoder?: new () => { decode(input: Uint8Array): string };
  TextEncoder?: new () => { encode(input: string): Uint8Array };
};

const host = () => globalThis as TextEncodingHost;

describe("ensureTextEncodingGlobals", () => {
  const originalDecoder = host().TextDecoder;
  const originalEncoder = host().TextEncoder;

  afterEach(() => {
    if (originalDecoder === undefined) {
      delete host().TextDecoder;
    } else {
      host().TextDecoder = originalDecoder;
    }
    if (originalEncoder === undefined) {
      delete host().TextEncoder;
    } else {
      host().TextEncoder = originalEncoder;
    }
    jest.resetModules();
  });

  it("installs TextDecoder and TextEncoder when missing", () => {
    delete host().TextDecoder;
    delete host().TextEncoder;

    const { ensureTextEncodingGlobals } = require("../textEncoding");
    ensureTextEncodingGlobals();

    expect(typeof host().TextDecoder).toBe("function");
    expect(typeof host().TextEncoder).toBe("function");
    const Dec = host().TextDecoder!;
    expect(new Dec().decode(new Uint8Array([104, 105]))).toBe("hi");
  });

  it("is a no-op when globals already exist", () => {
    class ExistingDecoder {}
    class ExistingEncoder {}
    host().TextDecoder = ExistingDecoder as unknown as TextEncodingHost["TextDecoder"];
    host().TextEncoder = ExistingEncoder as unknown as TextEncodingHost["TextEncoder"];

    const { ensureTextEncodingGlobals } = require("../textEncoding");
    ensureTextEncodingGlobals();

    expect(host().TextDecoder).toBe(ExistingDecoder);
    expect(host().TextEncoder).toBe(ExistingEncoder);
  });
});

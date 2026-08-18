/** @jest-environment node */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type TextEncodingHost = typeof globalThis & { TextDecoder?: any; TextEncoder?: any };

const encodingHost = () => globalThis as TextEncodingHost;

describe("ensureTextEncodingGlobals", () => {
  const originalDecoder = encodingHost().TextDecoder;
  const originalEncoder = encodingHost().TextEncoder;

  afterEach(() => {
    encodingHost().TextDecoder = originalDecoder;
    encodingHost().TextEncoder = originalEncoder;
    jest.resetModules();
  });

  it("installs TextDecoder and TextEncoder when missing", () => {
    encodingHost().TextDecoder = undefined;
    encodingHost().TextEncoder = undefined;

    const { ensureTextEncodingGlobals } = require("../textEncoding");
    ensureTextEncodingGlobals();

    expect(typeof encodingHost().TextDecoder).toBe("function");
    expect(typeof encodingHost().TextEncoder).toBe("function");
    const Dec = encodingHost().TextDecoder!;
    expect(new Dec().decode(new Uint8Array([104, 105]))).toBe("hi");
  });

  it("is a no-op when globals already exist", () => {
    class ExistingDecoder {}
    class ExistingEncoder {}
    encodingHost().TextDecoder = ExistingDecoder as unknown as TextEncodingHost["TextDecoder"];
    encodingHost().TextEncoder = ExistingEncoder as unknown as TextEncodingHost["TextEncoder"];

    const { ensureTextEncodingGlobals } = require("../textEncoding");
    ensureTextEncodingGlobals();

    expect(encodingHost().TextDecoder).toBe(ExistingDecoder);
    expect(encodingHost().TextEncoder).toBe(ExistingEncoder);
  });
});

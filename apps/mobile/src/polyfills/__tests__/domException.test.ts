/** @jest-environment node */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type DOMExceptionHost = typeof globalThis & { DOMException?: any };

const domHost = () => globalThis as DOMExceptionHost;

describe("ensureDOMExceptionGlobal", () => {
  const original = domHost().DOMException;

  afterEach(() => {
    domHost().DOMException = original;
    jest.resetModules();
  });

  it("installs DOMException when missing", () => {
    domHost().DOMException = undefined;
    const { ensureDOMExceptionGlobal } = require("../domException");
    ensureDOMExceptionGlobal();
    expect(typeof domHost().DOMException).toBe("function");
    const DOMEx = domHost().DOMException!;
    const err = new DOMEx("closed", "InvalidStateError");
    expect(err.name).toBe("InvalidStateError");
    expect(err.message).toBe("closed");
  });

  it("is a no-op when DOMException already exists", () => {
    class Existing {}
    domHost().DOMException = Existing as unknown as DOMExceptionHost["DOMException"];
    const { ensureDOMExceptionGlobal } = require("../domException");
    ensureDOMExceptionGlobal();
    expect(domHost().DOMException).toBe(Existing);
  });
});

/** @jest-environment node */

type DOMExceptionHost = typeof globalThis & {
  DOMException?: new (message?: string, name?: string) => Error;
};

const domHost = () => globalThis as DOMExceptionHost;

describe("ensureDOMExceptionGlobal", () => {
  const original = domHost().DOMException;

  afterEach(() => {
    if (original === undefined) {
      delete domHost().DOMException;
    } else {
      domHost().DOMException = original;
    }
    jest.resetModules();
  });

  it("installs DOMException when missing", () => {
    delete domHost().DOMException;
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

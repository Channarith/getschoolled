import { createTapCounter } from "../secretTaps";

describe("secret logo taps", () => {
  test("four quick taps trigger", () => {
    let t = 0;
    const c = createTapCounter({ now: () => t });
    expect([c.tap(), c.tap(), c.tap(), c.tap()]).toEqual([false, false, false, true]);
  });

  test("three taps, a pause, then one more does not trigger", () => {
    let t = 0;
    const c = createTapCounter({ now: () => t });
    c.tap(); t += 500; c.tap(); t += 500; c.tap();
    t += 3000;
    expect(c.tap()).toBe(false);
  });

  test("the window is per tap and resets after a trigger", () => {
    let t = 0;
    const c = createTapCounter({ now: () => t });
    for (let i = 0; i < 3; i += 1) { c.tap(); t += 2400; }
    expect(c.tap()).toBe(true);
    expect(c.tap()).toBe(false);
  });
});

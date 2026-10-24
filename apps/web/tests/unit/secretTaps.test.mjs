import test from "node:test";
import assert from "node:assert/strict";

import { createTapCounter, isPlainPointerClick, SECRET_PATH } from "../../app/lib/secretTaps.ts";

function clock() {
  let t = 1000;
  return { now: () => t, advance: (ms) => { t += ms; } };
}

test("four quick clicks trigger on the fourth only", () => {
  const c = clock();
  const counter = createTapCounter({ now: c.now });
  const results = [];
  for (let i = 0; i < 4; i += 1) { results.push(counter.tap()); c.advance(400); }
  assert.deepEqual(results, [false, false, false, true]);
});

test("three clicks, a long wait, then one more does not trigger", () => {
  const c = clock();
  const counter = createTapCounter({ now: c.now });
  counter.tap(); c.advance(300); counter.tap(); c.advance(300); counter.tap();
  c.advance(2600);
  assert.equal(counter.tap(), false);
});

test("each click only needs to be within 2.5s of the previous one", () => {
  const c = clock();
  const counter = createTapCounter({ now: c.now });
  for (let i = 0; i < 3; i += 1) { counter.tap(); c.advance(2400); }
  assert.equal(counter.tap(), true);
});

test("counter resets after triggering", () => {
  const c = clock();
  const counter = createTapCounter({ now: c.now });
  for (let i = 0; i < 4; i += 1) counter.tap();
  assert.equal(counter.tap(), false);
});

test("only plain primary pointer clicks count", () => {
  assert.equal(isPlainPointerClick({ button: 0, detail: 1 }), true);
  assert.equal(isPlainPointerClick({ button: 0, detail: 0 }), false);
  assert.equal(isPlainPointerClick({ button: 1, detail: 1 }), false);
  for (const key of ["ctrlKey", "metaKey", "shiftKey", "altKey"]) {
    assert.equal(isPlainPointerClick({ button: 0, detail: 1, [key]: true }), false);
  }
});

test("the secret goes to the on-the-go demo", () => {
  assert.equal(SECRET_PATH, "/demo/on-the-go");
});

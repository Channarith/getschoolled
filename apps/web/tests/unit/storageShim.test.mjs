import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";

import { STORAGE_SHIM_SCRIPT } from "../../app/lib/storageShimScript.mjs";

function sandbox(define) {
  const w = {};
  w.window = w;
  define(w);
  vm.createContext(w);
  vm.runInContext(STORAGE_SHIM_SCRIPT, w);
  return w;
}

const throwing = (name) => (w) =>
  Object.defineProperty(w, name, { get() { throw new Error("SecurityError: denied"); }, configurable: true });

test("a storage that throws on access is replaced by a working in-memory one", () => {
  const w = sandbox((x) => { throwing("localStorage")(x); throwing("sessionStorage")(x); });
  for (const name of ["localStorage", "sessionStorage"]) {
    const s = w[name];
    assert.equal(s.getItem("a"), null);
    s.setItem("a", 1);
    assert.equal(s.getItem("a"), "1");
    assert.equal(s.length, 1);
    assert.equal(s.key(0), "a");
    s.removeItem("a");
    assert.equal(s.getItem("a"), null);
    s.setItem("b", "2");
    s.clear();
    assert.equal(s.length, 0);
  }
});

test("a working storage is left exactly as it was", () => {
  const real = { getItem: () => "kept", setItem() {}, removeItem() {}, clear() {}, key: () => null, length: 0 };
  const w = sandbox((x) => { x.localStorage = real; x.sessionStorage = real; });
  assert.equal(w.localStorage, real);
  assert.equal(w.sessionStorage, real);
});

test("a full storage (setItem throws) keeps its saved data readable", () => {
  const full = { getItem: (k) => (k === "saved" ? "yes" : null), setItem() { throw new Error("QuotaExceededError"); } };
  const w = sandbox((x) => { x.localStorage = full; x.sessionStorage = full; });
  assert.equal(w.localStorage, full);
  assert.equal(w.localStorage.getItem("saved"), "yes");
});

test("only the throwing one is replaced", () => {
  const real = { getItem: () => null, setItem() {} };
  const w = sandbox((x) => { throwing("localStorage")(x); x.sessionStorage = real; });
  assert.equal(w.sessionStorage, real);
  w.localStorage.setItem("k", "v");
  assert.equal(w.localStorage.getItem("k"), "v");
});

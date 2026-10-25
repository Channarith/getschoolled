import test from "node:test";
import assert from "node:assert/strict";

import { shouldBlockOfflineNavigation } from "../../app/lib/offlineGate.mjs";

test("offline blocks the navigation", () => assert.equal(shouldBlockOfflineNavigation({ onLine: false }), true));
test("online lets it through", () => assert.equal(shouldBlockOfflineNavigation({ onLine: true }), false));
test("unknown connectivity lets the browser try", () => {
  assert.equal(shouldBlockOfflineNavigation(null), false);
  assert.equal(shouldBlockOfflineNavigation({}), false);
  assert.equal(shouldBlockOfflineNavigation({ onLine: "no" }), false);
});

import test from "node:test";
import assert from "node:assert/strict";

import { secretHeaderFallbackAllowed } from "../../app/lib/adminBffPolicy.ts";

test("in a cloud deployment a visitor-supplied admin secret is never forwarded", () => {
  assert.equal(secretHeaderFallbackAllowed({ DEPLOY_MODE: "cloud" }), false);
  assert.equal(secretHeaderFallbackAllowed({ DEPLOY_MODE: "production" }), false);
  assert.equal(secretHeaderFallbackAllowed({ DEPLOY_MODE: "staging" }), false);
});

test("local, dev and test keep the header fallback; an explicit opt-in restores it in the cloud", () => {
  for (const mode of ["local", "dev", "development", "test", "debug"]) assert.equal(secretHeaderFallbackAllowed({ DEPLOY_MODE: mode }), true);
  assert.equal(secretHeaderFallbackAllowed({}), true);
  assert.equal(secretHeaderFallbackAllowed({ DEPLOY_MODE: "cloud", ADMIN_BFF_ALLOW_SECRET_HEADER: "1" }), true);
  assert.equal(secretHeaderFallbackAllowed({ DEPLOY_MODE: "cloud", ADMIN_BFF_ALLOW_SECRET_HEADER: "true" }), false);
});

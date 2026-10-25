import test from "node:test";
import assert from "node:assert/strict";

import nextConfig from "../../next.config.mjs";

const headers = async () => Object.fromEntries((await nextConfig.headers())[0].headers.map((h) => [h.key, h.value]));

test("the enforced policy keeps framing locked and the report-only policy is wider but never allows plugins or foreign bases", async () => {
  const h = await headers();
  assert.equal(h["Content-Security-Policy"], "frame-ancestors 'self'");
  const ro = h["Content-Security-Policy-Report-Only"];
  assert.ok(ro.includes("object-src 'none'") && ro.includes("base-uri 'self'") && ro.includes("form-action 'self'"));
  assert.ok(!/script-src[^;]*\*/.test(ro), "no wildcard script source");
  assert.ok(ro.includes("'wasm-unsafe-eval'"), "vision models need wasm");
});

test("camera and microphone stay available to this page only", async () => {
  const pp = (await headers())["Permissions-Policy"];
  assert.ok(pp.includes("camera=(self)") && pp.includes("microphone=(self)") && pp.includes("geolocation=()"));
});

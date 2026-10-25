import test from "node:test";
import assert from "node:assert/strict";

import { safeReturnPath } from "../../app/lib/safeRedirect.ts";

test("same-site paths pass through", () => {
  for (const ok of ["/courses", "/account?tab=voice", "/demo/drivers-ed#top", "/a/b/c"]) assert.equal(safeReturnPath(ok, "/x"), ok);
});

test("anything that could leave the site falls back", () => {
  const bad = [
    "https://evil.example", "http://evil.example/x", "//evil.example", "/\\evil.example", "\\\\evil.example", "javascript:alert(1)",
    "data:text/html,x", "/ok\r\nSet-Cookie:x", "/ok\nnot", "/ok\\..\\evil", "evil.example", "", "   ", null, undefined, "/" + "a".repeat(600),
  ];
  for (const b of bad) assert.equal(safeReturnPath(b, "/fallback"), "/fallback", String(b).slice(0, 40));
});

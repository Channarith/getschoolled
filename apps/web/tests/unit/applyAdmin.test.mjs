import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const src = readFileSync(new URL("../../app/lib/api.ts", import.meta.url), "utf8");
const body = src.slice(src.indexOf("export function applyAdmin"), src.indexOf("function authHeaders"));

test("applyAdmin returns early when the flag is already set, so listeners that re-fetch /auth/me cannot loop", () => {
  assert.match(body, /if \(!isAdmin \|\| isAdminUnlocked\(\)\) return;/);
  assert.ok(body.indexOf("isAdminUnlocked()") < body.indexOf("notifyAuthChange()"));
});

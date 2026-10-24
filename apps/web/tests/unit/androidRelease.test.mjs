import test from "node:test";
import assert from "node:assert/strict";

import {
  compareVersions,
  fetchManifest,
  parseManifest,
  resetManifestCacheForTests,
} from "../../app/lib/androidRelease.ts";

const GOOD = {
  version: "0.97.12",
  url: "https://salareen-prod.sjc1.vultrobjects.com/releases/android/v0.97.12/app-release.apk",
  sha256: "a".repeat(64),
  versionCode: 9712,
  min_supported: "0.95.0",
};

test("a good manifest parses", () => {
  const m = parseManifest(GOOD);
  assert.equal(m?.version, "0.97.12");
  assert.equal(m?.min_supported, "0.95.0");
  assert.equal(m?.sha256, "a".repeat(64));
});

test("a manifest cannot point the download route at another host", () => {
  assert.equal(parseManifest({ ...GOOD, url: "https://evil.example.com/app.apk" }), null);
  assert.equal(parseManifest({ ...GOOD, url: "http://salareen-prod.sjc1.vultrobjects.com/app.apk" }), null);
  assert.equal(parseManifest({ ...GOOD, url: "javascript:alert(1)" }), null);
  assert.equal(parseManifest({ ...GOOD, version: "latest" }), null);
  assert.equal(parseManifest(null), null);
});

test("an https url on the manifest's own host is accepted", () => {
  const m = parseManifest({ ...GOOD, url: "https://cdn.example.org/a.apk" }, "https://cdn.example.org/latest.json");
  assert.equal(m?.url, "https://cdn.example.org/a.apk");
});

test("bad sha256 and min_supported are dropped, not trusted", () => {
  const m = parseManifest({ ...GOOD, sha256: "xyz", min_supported: "soon" });
  assert.equal(m?.sha256, undefined);
  assert.equal(m?.min_supported, undefined);
});

test("version comparison", () => {
  assert.equal(compareVersions("0.97.12", "0.97.2"), 1);
  assert.equal(compareVersions("0.97.2", "0.97.12"), -1);
  assert.equal(compareVersions("1.0.0", "1.0.0"), 0);
});

test("manifest is cached and failures fall back to null without throwing", async () => {
  resetManifestCacheForTests();
  let calls = 0;
  const ok = async () => {
    calls += 1;
    return { ok: true, json: async () => GOOD };
  };
  const a = await fetchManifest({}, ok, 1_000);
  const b = await fetchManifest({}, ok, 2_000);
  assert.equal(a?.version, "0.97.12");
  assert.equal(b?.version, "0.97.12");
  assert.equal(calls, 1, "second call within the ttl is served from cache");

  resetManifestCacheForTests();
  const down = async () => {
    throw new Error("network down");
  };
  assert.equal(await fetchManifest({}, down, 1_000), null);

  resetManifestCacheForTests();
  const bad = async () => ({ ok: false, status: 503, json: async () => ({}) });
  assert.equal(await fetchManifest({}, bad, 1_000), null);
});

test("a later outage keeps serving the last good manifest", async () => {
  resetManifestCacheForTests();
  const ok = async () => ({ ok: true, json: async () => GOOD });
  await fetchManifest({}, ok, 1_000);
  const down = async () => {
    throw new Error("network down");
  };
  const again = await fetchManifest({}, down, 1_000 + 120_000);
  assert.equal(again?.version, "0.97.12");
});

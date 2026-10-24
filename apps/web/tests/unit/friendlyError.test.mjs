import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { classifyStatus, KIND_MOOD } from "../../../../packages/shared/friendly_error/classify.mjs";
import { moodSvg, MOODS } from "../../../../packages/shared/friendly_error/art.mjs";
import { buildAll } from "../../../../scripts/build_friendly_errors.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const COPY = JSON.parse(readFileSync(join(ROOT, "packages/shared/friendly_error/copy.json"), "utf8"));

test("every failure maps to the right friendly screen", () => {
  assert.equal(classifyStatus(404), "notfound");
  assert.equal(classifyStatus(410), "notfound");
  assert.equal(classifyStatus(501), "notimpl");
  for (const code of [502, 503, 504, 522]) assert.equal(classifyStatus(code), "network", String(code));
  assert.equal(classifyStatus(500), "oops");
  assert.equal(classifyStatus(599), "oops");
  assert.equal(classifyStatus(0), "network");
  assert.equal(classifyStatus(undefined), "network");
  assert.equal(classifyStatus(200, { offline: true }), "offline");
  assert.equal(classifyStatus(401), null);
  assert.equal(classifyStatus(422), null);
});

test("each kind has a mascot mood and copy in en, es and km", () => {
  for (const kind of ["offline", "network", "notfound", "notimpl", "oops"]) {
    assert.ok(MOODS.includes(KIND_MOOD[kind]), `${kind} has a mood`);
    for (const locale of ["en", "es", "km"]) {
      const row = COPY[locale][kind];
      assert.ok(row?.title && row?.body && row?.hint, `${locale}.${kind}`);
      assert.ok(!/not found|something went wrong/i.test(`${row.title} ${row.body}`) || locale !== "en" || kind === "notfound" && /can't find/i.test(row.title), `${locale}.${kind} is not generic`);
    }
  }
  for (const locale of ["en", "es", "km"]) {
    for (const key of ["tryAgain", "retryIn", "home", "back", "status", "checking", "stillDown"]) {
      assert.ok(COPY[locale].common[key], `${locale}.common.${key}`);
    }
    assert.match(COPY[locale].common.retryIn, /\{n\}/);
    assert.match(COPY[locale].common.status, /\{code\}/);
  }
});

test("the mascot art is self-contained and accessible", () => {
  for (const mood of MOODS) {
    const svg = moodSvg(mood);
    assert.match(svg, /role="img"/);
    assert.match(svg, /<title>/);
    assert.ok(!/(?:href|src)=|url\(['"]?https?:/i.test(svg), `${mood} loads nothing external`);
    assert.match(svg, /prefers-reduced-motion/);
    assert.ok(!/<style>/.test(moodSvg(mood, { animated: false })), "static art has no CSS (React Native)");
  }
});

test("generated files for every platform are up to date", () => {
  for (const [rel, content] of Object.entries(buildAll())) {
    const file = join(ROOT, rel);
    assert.ok(existsSync(file), `${rel} exists`);
    assert.equal(readFileSync(file, "utf8"), content, `${rel} is stale: run node scripts/build_friendly_errors.mjs`);
  }
});

test("ingress pages cover 404, 500, 502, 503 and 504 for browsers and API clients", () => {
  const manifest = buildAll()["infra/k8s-vke/friendly-errors.yaml"];
  for (const code of [404, 500, 502, 503, 504]) {
    assert.ok(manifest.includes(`  ${code}.html: |`), `${code}.html`);
    assert.ok(manifest.includes(`  ${code}.json: |`), `${code}.json`);
  }
  assert.match(manifest, /X-Format|x_format/);
});

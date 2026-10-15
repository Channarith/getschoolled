import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { OPENCV_JS_URL, ModelLoadError, waitForCvRuntime } from "../../app/lib/opencvRuntime.ts";

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, "..", "..");
const vendored = join(web, "public", "opencv", "4.10.0", "opencv.js");

test("opencv.js is served from our own origin", () => {
  assert.equal(OPENCV_JS_URL, "/opencv/4.10.0/opencv.js");
  assert.ok(statSync(vendored).size > 9_000_000, "vendored opencv.js is present");
});

test("no runtime code points at docs.opencv.org", () => {
  const offenders = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (/\.(ts|tsx|mjs|js)$/.test(name) && readFileSync(path, "utf8").includes("docs.opencv.org")) {
        offenders.push(path);
      }
    }
  };
  walk(join(web, "app"));
  assert.deepEqual(offenders, []);
});

test("the vendored build initialises and has YuNet + readNet", { timeout: 90_000 }, async () => {
  const require = createRequire(import.meta.url);
  const cv = await waitForCvRuntime(require(vendored), 80_000);
  assert.equal(typeof cv.FaceDetectorYN, "function");
  assert.equal(typeof cv.readNet, "function");
  assert.equal(typeof cv.FS_createDataFile, "function");
  assert.equal(typeof cv.FS_unlink, "function");
  assert.equal("then" in cv, false, "self-thenable removed so await cannot hang");
});

test("a missing or incomplete runtime is a model error, not a camera error", async () => {
  await assert.rejects(waitForCvRuntime(undefined), ModelLoadError);
  await assert.rejects(waitForCvRuntime({ Mat: function Mat() {} }), /FaceDetectorYN/);
  await assert.rejects(waitForCvRuntime({}, 30), ModelLoadError);
});

test("rating scale is a 5-column grid with touch-size buttons", () => {
  const css = readFileSync(join(web, "app", "onboarding", "Onboarding.module.css"), "utf8");
  const scale = css.match(/\.scale \{[^}]*\}/)?.[0] ?? "";
  assert.match(scale, /repeat\(5, minmax\(0, 1fr\)\)/);
  const button = css.match(/\.scale button \{[^}]*\}/)?.[0] ?? "";
  assert.match(button, /padding: 0;/);
  assert.match(button, /min-height: 44px;/);
});

test("setup copy never says Face ID", () => {
  for (const file of ["app/components/BiometricSetupAssistant.tsx", "app/onboarding/page.tsx"]) {
    const source = readFileSync(join(web, file), "utf8");
    assert.doesNotMatch(source, /Face (&amp; |& )?Voice ID|Face ID|Audio ID/, file);
    assert.doesNotMatch(source, /first name/i, file);
  }
});

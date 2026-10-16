import test from "node:test";
import assert from "node:assert/strict";
import {
  AGE_MAX,
  AGE_MIN,
  AGE_OPTIONS,
  POSES,
  clampAge,
  describeMediaError,
  faceContour,
  faceGeometry,
  levelFromTimeDomain,
  lightingAction,
  meanLuma,
  pickRecorderMime,
  poseFromBaseline,
  shuffledPoses,
  svgPath,
  waveformBars,
} from "../../app/lib/learnerCheck.ts";

// YuNet order: right eye, left eye, nose, right mouth corner, left mouth corner.
const FRONTAL = [[247, 121], [312, 121], [279, 151], [248, 179], [308, 180]];

test("age picker offers every age from 3 to 120", () => {
  assert.equal(AGE_MIN, 3);
  assert.equal(AGE_MAX, 120);
  assert.equal(AGE_OPTIONS.length, 118);
  assert.deepEqual([AGE_OPTIONS[0], AGE_OPTIONS.at(-1)], [3, 120]);
  assert.equal(clampAge(1), 3);
  assert.equal(clampAge(200), 120);
});

test("look targets are a random order of all four directions", () => {
  const seen = new Set();
  let seed = 1;
  const rng = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 40; i += 1) {
    const order = shuffledPoses(rng);
    assert.deepEqual([...order].sort(), [...POSES].sort());
    seen.add(order.join(","));
  }
  assert.ok(seen.size > 5, `expected varied orders, got ${seen.size}`);
});

test("pose is read from the mirrored head turn relative to neutral", () => {
  const base = faceGeometry(FRONTAL, [220, 80, 120, 140], [560, 420]);
  assert.ok(base);
  const shift = (dx, dy) => FRONTAL.map(([x, y], i) => (i === 2 ? [x + dx, y + dy] : [x, y]));
  const geo = (dx, dy) => faceGeometry(shift(dx, dy), [220, 80, 120, 140], [560, 420]);
  assert.equal(poseFromBaseline(base, geo(0, 0)), null);
  assert.equal(poseFromBaseline(base, geo(-14, 0)), "right");
  assert.equal(poseFromBaseline(base, geo(14, 0)), "left");
  assert.equal(poseFromBaseline(base, geo(0, -8)), "up");
  assert.equal(poseFromBaseline(base, geo(0, 8)), "down");
});

test("contour wraps the landmarks and is hidden without them", () => {
  const contour = faceContour(FRONTAL);
  assert.ok(contour);
  assert.equal(contour.outline.length, 32);
  const xs = contour.outline.map(([x]) => x);
  const ys = contour.outline.map(([, y]) => y);
  for (const [x, y] of FRONTAL) {
    assert.ok(x > Math.min(...xs) && x < Math.max(...xs), "landmark x inside outline");
    assert.ok(y > Math.min(...ys) && y < Math.max(...ys), "landmark y inside outline");
  }
  assert.ok(Math.min(...ys) < 121 - 30, "outline reaches the forehead");
  assert.ok(Math.max(...ys) > 180 + 20, "outline reaches the chin");
  assert.equal(contour.rightEye.length, 6);
  assert.deepEqual(contour.nose[1], FRONTAL[2]);
  assert.equal(faceContour(null), null);
  assert.equal(faceContour([[1, 1]]), null);
  assert.equal(faceContour([[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]), null);
  assert.equal(faceContour([[NaN, 1], [2, 2], [3, 3], [4, 4], [5, 5]]), null);
});

test("contour follows a tilted face", () => {
  const angle = 0.3;
  const rotate = ([x, y]) => [
    280 + (x - 280) * Math.cos(angle) - (y - 150) * Math.sin(angle),
    150 + (x - 280) * Math.sin(angle) + (y - 150) * Math.cos(angle),
  ];
  const straight = faceContour(FRONTAL);
  const tilted = faceContour(FRONTAL.map(rotate));
  const near = (a, b) => Math.abs(a - b) < 0.5;
  straight.outline.forEach((point, i) => {
    const expected = rotate(point);
    assert.ok(near(tilted.outline[i][0], expected[0]) && near(tilted.outline[i][1], expected[1]));
  });
});

test("svg paths are closed only when asked", () => {
  assert.equal(svgPath([]), "");
  assert.equal(svgPath([[1, 2], [3.25, 4]]), "M1.0 2.0 L3.3 4.0");
  assert.match(svgPath([[1, 2], [3, 4]], true), / Z$/);
});

test("lighting uses the torch when present, else the white screen", () => {
  const dark = new Uint8ClampedArray(4 * 64).fill(20);
  const bright = new Uint8ClampedArray(4 * 64).fill(180);
  assert.ok(meanLuma(dark, 1) < 0.1);
  assert.ok(meanLuma(bright, 1) > 0.6);
  assert.equal(lightingAction(meanLuma(bright, 1), true), "none");
  assert.equal(lightingAction(meanLuma(dark, 1), true), "torch");
  assert.equal(lightingAction(meanLuma(dark, 1), false), "screen");
});

test("waveform fills left to right and follows the level", () => {
  const samples = [];
  for (let t = 0; t < 5; t += 0.05) samples.push({ t, level: t < 2 ? 0.2 : 0.8 });
  const bars = waveformBars(samples, 10, 20);
  assert.equal(bars.length, 20);
  assert.ok(bars.slice(0, 4).every((h) => Math.abs(h - 0.2) < 1e-9));
  assert.ok(bars.slice(4, 10).every((h) => Math.abs(h - 0.8) < 1e-9));
  assert.ok(bars.slice(10).every((h) => h === 0), "future bars stay empty");
  assert.deepEqual(waveformBars([{ t: 12, level: 1 }, { t: -1, level: 1 }], 10, 4), [0, 0, 0, 0]);
  assert.deepEqual(waveformBars([{ t: 0, level: 3 }], 10, 2), [1, 0]);
});

test("mic level is 0 for silence and grows with amplitude", () => {
  const silence = new Uint8Array(512).fill(128);
  const quiet = Uint8Array.from({ length: 512 }, (_, i) => 128 + Math.round(6 * Math.sin(i / 4)));
  const loud = Uint8Array.from({ length: 512 }, (_, i) => 128 + Math.round(90 * Math.sin(i / 4)));
  assert.equal(levelFromTimeDomain(silence), 0);
  assert.ok(levelFromTimeDomain(quiet) > 0);
  assert.ok(levelFromTimeDomain(loud) > levelFromTimeDomain(quiet));
  assert.ok(levelFromTimeDomain(loud) <= 1);
});

test("recorder picks webm on Chrome, mp4 on Safari, default otherwise", () => {
  const chrome = (type) => type.startsWith("audio/webm");
  const safari = (type) => type.startsWith("audio/mp4");
  assert.equal(pickRecorderMime(chrome), "audio/webm;codecs=opus");
  assert.equal(pickRecorderMime(safari), "audio/mp4;codecs=mp4a.40.2");
  assert.equal(pickRecorderMime(() => false), "");
  assert.equal(pickRecorderMime(undefined), "");
  assert.equal(pickRecorderMime(() => { throw new Error("x"); }), "");
});

test("camera permission and model failures are told apart", () => {
  assert.equal(describeMediaError({ name: "NotAllowedError" }, "camera").kind, "permission");
  assert.equal(describeMediaError({ name: "NotFoundError" }, "microphone").kind, "missing");
  assert.equal(describeMediaError({ name: "NotReadableError" }, "camera").kind, "busy");
  const model = describeMediaError({ name: "ModelLoadError", message: "failed to load opencv.js" }, "camera");
  assert.equal(model.kind, "model");
  assert.doesNotMatch(model.message, /Camera unavailable/);
  assert.match(describeMediaError({ name: "NotAllowedError" }, "microphone").message, /Microphone access is blocked/);
});

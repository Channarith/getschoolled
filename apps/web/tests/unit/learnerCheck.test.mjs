import test from "node:test";
import assert from "node:assert/strict";
import {
  AGE_MAX,
  AGE_MIN,
  AGE_OPTIONS,
  POSES,
  clampAge,
  describeMediaError,
  FACE_MARK_REGIONS,
  MESH_SOURCE_LANDMARKS,
  bytesFromBase64,
  faceContour,
  faceGeometry,
  faceMarks,
  decodeJpegLuma,
  faceMarksFromJpeg,
  levelFromTimeDomain,
  lightingAction,
  meanLuma,
  pickRecorderMime,
  poseFromBaseline,
  shuffledPoses,
  stableFaceMarks,
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
  // Raw-frame yaw is flipped for the mirrored selfie the learner sees.
  assert.equal(poseFromBaseline(base, geo(14, 0), false), "right");
  assert.equal(poseFromBaseline(base, geo(-14, 0), false), "left");
});

// Rigid head, mm, projected to pixels. +yaw turns the nose toward the person's
// left eye (right side of an unmirrored frame). +pitch looks down.
// Mouth sits well forward of the eyes, which is what cancelled the old
// nose-vs-mouth-axis yaw.
function projectHead(yawDeg, pitchDeg, rollDeg = 0) {
  const iod = 63;
  const pts = [
    [-iod / 2, 0, 0],
    [iod / 2, 0, 0],
    [0, 32, 30],
    [-25, 68, 18],
    [25, 68, 18],
  ];
  const yaw = (yawDeg * Math.PI) / 180;
  const pitch = (pitchDeg * Math.PI) / 180;
  const roll = (rollDeg * Math.PI) / 180;
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const cr = Math.cos(roll);
  const sr = Math.sin(roll);
  return pts.map(([x, y, z]) => {
    const x1 = x * cy + z * sy;
    const z1 = -x * sy + z * cy;
    const y2 = y * cp + z1 * sp;
    const x3 = x1 * cr - y2 * sr;
    const y3 = x1 * sr + y2 * cr;
    return [320 + x3 * 3.2, 180 + y3 * 3.2];
  });
}

const HEAD_BOX = [220, 80, 200, 260];
const HEAD_FRAME = [640, 480];

function oldAxisYaw(landmarks) {
  const [rightEye, leftEye, nose, rightMouth, leftMouth] = landmarks;
  const eyeMidX = (rightEye[0] + leftEye[0]) / 2;
  const mouthMidX = (rightMouth[0] + leftMouth[0]) / 2;
  const eyeDist = Math.hypot(leftEye[0] - rightEye[0], leftEye[1] - rightEye[1]);
  return (nose[0] - (eyeMidX + mouthMidX) / 2) / eyeDist;
}

test("a clear look registers even when the mouth shift used to hide it", () => {
  const neutralLm = projectHead(0, 0);
  const neutral = faceGeometry(neutralLm, HEAD_BOX, HEAD_FRAME);
  assert.ok(neutral);
  const turned = projectHead(20, 0);
  const geometry = faceGeometry(turned, HEAD_BOX, HEAD_FRAME);
  // The previous gate (nose vs the eye/mouth axis, threshold 0.16) missed this.
  const hidden = Math.abs(oldAxisYaw(turned) - oldAxisYaw(neutralLm));
  assert.ok(hidden < 0.16, `expected the old yaw to miss, got ${hidden}`);
  assert.equal(poseFromBaseline(neutral, geometry), "left");
  assert.equal(poseFromBaseline(neutral, faceGeometry(projectHead(-20, 0), HEAD_BOX, HEAD_FRAME)), "right");
  assert.equal(poseFromBaseline(neutral, faceGeometry(projectHead(0, -12), HEAD_BOX, HEAD_FRAME)), "up");
  assert.equal(poseFromBaseline(neutral, faceGeometry(projectHead(0, 12), HEAD_BOX, HEAD_FRAME)), "down");
  // A tilted head still counts as the prompted left, not up or down.
  assert.equal(poseFromBaseline(neutral, faceGeometry(projectHead(20, 0, 25), HEAD_BOX, HEAD_FRAME)), "left");
  assert.equal(poseFromBaseline(neutral, faceGeometry(projectHead(5, 4), HEAD_BOX, HEAD_FRAME)), null);
  assert.equal(poseFromBaseline(neutral, geometry, false), "right");
});

test("geometry is absent when landmarks cannot describe a face", () => {
  assert.equal(faceGeometry(null, [0, 0, 10, 10], [100, 100]), null);
  assert.equal(faceGeometry([[1, 1], [2, 2]], [0, 0, 10, 10], [100, 100]), null);
  assert.equal(faceGeometry([[0, 0], [0, 0], [0, 0], [0, 0], [1, 1]], [0, 0, 10, 10], [100, 100]), null);
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

test("mesh is an estimated grid, not a dense landmarker, and stays inside the outline", () => {
  assert.equal(MESH_SOURCE_LANDMARKS, 5);
  const contour = faceContour(FRONTAL);
  assert.ok(contour.grid.length >= 12);
  assert.ok(contour.grid.length < 40);
  const xs = contour.outline.map(([x]) => x);
  const ys = contour.outline.map(([, y]) => y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  let widest = 0;
  for (const line of contour.grid) {
    assert.ok(line.length >= 2);
    const lineXs = line.map(([x]) => x);
    widest = Math.max(widest, Math.max(...lineXs) - Math.min(...lineXs));
    for (const [x, y] of line) {
      assert.ok(x > minX - 3 && x < maxX + 3, `grid x ${x} outside outline`);
      assert.ok(y > minY - 3 && y < maxY + 3, `grid y ${y} outside outline`);
    }
  }
  assert.ok(widest > 50, "a grid line crosses the cheeks");
  const plain = faceContour(FRONTAL);
  const ignored = faceContour(FRONTAL, [0, 0, 0, 0]);
  assert.deepEqual(ignored.outline, plain.outline);
  const span = (shape) => {
    const values = shape.outline.map(([, y]) => y);
    return Math.max(...values) - Math.min(...values);
  };
  const boxed = faceContour(FRONTAL, 32, [180, 10, 220, 340]);
  assert.ok(span(boxed) <= span(plain) * 1.25 + 1);
  assert.ok(span(boxed) >= span(plain) * 0.85 - 1);
  for (const [x, y] of FRONTAL) {
    const bxs = boxed.outline.map(([px]) => px);
    const bys = boxed.outline.map(([, py]) => py);
    assert.ok(x > Math.min(...bxs) && x < Math.max(...bxs));
    assert.ok(y > Math.min(...bys) && y < Math.max(...bys));
  }
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
  straight.grid.forEach((line, lineIndex) => {
    line.forEach((point, i) => {
      const expected = rotate(point);
      const got = tilted.grid[lineIndex][i];
      assert.ok(Math.hypot(got[0] - expected[0], got[1] - expected[1]) < 1.5);
    });
  });
});

function paintFace(spots) {
  const width = 420;
  const height = 380;
  const rgba = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < rgba.length; i += 4) {
    rgba[i] = 214;
    rgba[i + 1] = 166;
    rgba[i + 2] = 140;
    rgba[i + 3] = 255;
  }
  for (const spot of spots) {
    const [x0, y0, n, rgb] = spot;
    for (let y = y0; y < y0 + n; y += 1) {
      for (let x = x0; x < x0 + n; x += 1) {
        if (x < 0 || y < 0 || x >= width || y >= height) continue;
        const i = (y * width + x) * 4;
        rgba[i] = rgb[0];
        rgba[i + 1] = rgb[1];
        rgba[i + 2] = rgb[2];
      }
    }
  }
  return { rgba, width, height };
}

test("marks note a cheek spot and skip eyes, mouth, and an empty face", () => {
  assert.ok(FACE_MARK_REGIONS.includes("left cheek"));
  const dark = [40, 28, 24];
  const clear = paintFace([]);
  assert.deepEqual(faceMarks(clear.rgba, clear.width, clear.height, FRONTAL), []);
  const cheek = paintFace([[304, 142, 16, dark]]);
  const marks = faceMarks(cheek.rgba, cheek.width, cheek.height, FRONTAL);
  assert.equal(marks.length, 1);
  assert.equal(marks[0].region, "left cheek");
  assert.ok(marks[0].contrast > 0.1);
  const eye = paintFace([[306, 115, 12, dark]]);
  assert.deepEqual(faceMarks(eye.rgba, eye.width, eye.height, FRONTAL), []);
  const mouth = paintFace([[272, 173, 14, dark]]);
  assert.deepEqual(faceMarks(mouth.rgba, mouth.width, mouth.height, FRONTAL), []);
  assert.deepEqual(faceMarks(cheek.rgba, cheek.width, cheek.height, null), []);
});

test("a mark has to repeat before the live mesh keeps it", () => {
  const mark = { region: "left cheek", point: [10, 20], contrast: 0.4 };
  assert.deepEqual(stableFaceMarks([[mark], [mark]], 3), []);
  const kept = stableFaceMarks([[mark], [mark], [{ ...mark, point: [14, 22] }]], 3);
  assert.equal(kept.length, 1);
  assert.equal(kept[0].region, "left cheek");
  assert.ok(Math.abs(kept[0].point[0] - (10 + 10 + 14) / 3) < 0.01);
  assert.deepEqual(stableFaceMarks([], 3), []);
});

test("base64 round-trips and a non-jpeg yields no marks", () => {
  const bytes = bytesFromBase64("aGk=");
  assert.deepEqual([...bytes], [104, 105]);
  assert.equal(bytesFromBase64("@@@@"), null);
  assert.deepEqual(faceMarksFromJpeg("aGk=", FRONTAL, [2, 2]), []);
});


const GRAY_JPEG = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAYACADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD8f6KKKACiiigAooooAKKKKAP/2Q==";
const CHEEK_JPEG = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAF8AaQDAREAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD7Er8rP2gKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgD5t/4e7f8E8f+jg//AC09W/8AkSvR/snMP5PxX+Z5f9tZZ/z8/CX+Qf8AD3b/AIJ4/wDRwf8A5aerf/IlH9k5h/J+K/zD+2ss/wCfn4S/yPpKvOPUCgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoA/m3r9EPy8KAP6SK/Oz9QCgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoA/En/h0T/wUO/6N8/8ALs0n/wCS6+z/ALWy/wDn/B/5Hwf9i5n/AM+/xj/mH/Don/god/0b5/5dmk//ACXR/a2X/wA/4P8AyD+xcz/59/jH/M/bavjD7wKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgAoAKACgD//Z";

test("a baseline jpeg yields luma, and a cheek spot survives the still decoder", () => {
  const gray = decodeJpegLuma(bytesFromBase64(GRAY_JPEG), 64);
  assert.ok(gray);
  assert.deepEqual([gray.sourceWidth, gray.sourceHeight], [32, 24]);
  let sum = 0;
  const n = gray.width * gray.height;
  for (let i = 0; i < gray.rgba.length; i += 4) sum += gray.rgba[i];
  assert.ok(Math.abs(sum / n - 32) < 3);
  assert.deepEqual(faceMarksFromJpeg(CHEEK_JPEG, FRONTAL, [100, 100]), []);
  const marks = faceMarksFromJpeg(CHEEK_JPEG, FRONTAL, [420, 380]);
  assert.equal(marks.length, 1);
  assert.equal(marks[0].region, "left cheek");
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

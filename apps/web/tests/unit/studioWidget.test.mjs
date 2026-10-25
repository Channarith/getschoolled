// Course Studio panel: the tracking canvas must anchor to the camera tile, and the landmark -> canvas mapping must be centred.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const studio = readFileSync(new URL("../../../../subrepos/theodore_course_studio/src/theodore_course_studio/studio_page.py", import.meta.url), "utf8");
const voiceJs = readFileSync(new URL("../../../../subrepos/theodore_course_studio/src/theodore_course_studio/voice_static/course_voice.js", import.meta.url), "utf8");

test("inside the panel the camera tile is a positioned box, so its absolute tracking canvas anchors to it (not to the panel corner)", () => {
  assert.match(studio, /\.student-cam-track \{ position:absolute; top:0; left:0;/);
  for (const body of ["course-clean", "demo-widget"]) {
    const rule = studio.match(new RegExp(`html body\\.${body} #course-widget #student-cam \\{ position:(\\w+) !important;`));
    assert.ok(rule, `${body} rule found`);
    assert.equal(rule[1], "relative", `${body}: #student-cam must be position:relative (static makes the canvas jump to the panel's top-left)`);
  }
});

test("the panel shows no sentences: status is a dot with a tooltip, the camera's own Hide/status text is not shown", () => {
  assert.match(studio, /#course-widget \.student-cam-hide, #course-widget \.student-cam-status, #course-widget \.student-cam-note \{ display:none !important; \}/);
  assert.match(studio, /#course-widget \.cw-status::before/);
  assert.match(voiceJs, /cw\.status\.title = text;/);
  assert.match(studio, /#sample-clock small \{ display:none;/);
});

test("lessonTrackXY maps a landmark to the right canvas point for a cover-fitted video", () => {
  const src = studio.match(/function lessonTrackXY\(nx, ny, video, w, h\) \{[\s\S]*?\n    \}\n/)[0];
  const lessonTrackXY = new Function(`${src}; return lessonTrackXY;`)();
  const wide = { videoWidth: 1920, videoHeight: 1080 };
  const four3 = { videoWidth: 640, videoHeight: 480 };
  const portrait = { videoWidth: 480, videoHeight: 640 };
  for (const video of [wide, four3, portrait]) {
    const c = lessonTrackXY(0.5, 0.5, video, 320, 180);
    assert.ok(Math.abs(c.x - 160) < 1e-6 && Math.abs(c.y - 90) < 1e-6, "image centre = canvas centre");
  }
  // A 4:3 picture cover-fitted into 16:9 is cropped top and bottom: its top-left corner lies outside the canvas vertically.
  const corner = lessonTrackXY(0, 0, four3, 320, 180);
  assert.equal(corner.x, 0);
  assert.ok(corner.y < 0);
  const wideCorner = lessonTrackXY(1, 1, wide, 320, 180);
  assert.ok(Math.abs(wideCorner.x - 320) < 1e-6 && Math.abs(wideCorner.y - 180) < 1e-6);
});

import test from "node:test";
import assert from "node:assert/strict";

import { onTheGoExperience, sampleCourses, timerLabel, ON_THE_GO_DEMO_SECONDS } from "../../app/lib/onTheGoMode.ts";

test("demo mode shows the 10-minute timer and does not enable Sala", () => {
  const demo = onTheGoExperience("demo");
  assert.equal(demo.showTimer, true);
  assert.equal(demo.sampleSeconds, ON_THE_GO_DEMO_SECONDS);
  assert.equal(demo.sampleSeconds, 600);
  assert.equal(demo.salaAgent, false);
  assert.equal(demo.fullCatalog, false);
  assert.equal(timerLabel(600), "10:00");
  assert.equal(timerLabel(65), "1:05");
});

test("full mode has no timer and enables the Sala agent", () => {
  const full = onTheGoExperience("full");
  assert.equal(full.showTimer, false);
  assert.equal(full.sampleSeconds, 0);
  assert.equal(full.salaAgent, true);
  assert.equal(full.fullCatalog, true);
});

test("the demo keeps a single sample course", () => {
  const rows = [
    { id: "algebra", title: "Algebra", category: "Math" },
    { id: "drivers-ed", title: "Driver's Education", category: "Safety" },
    { id: "cooking", title: "Cooking", category: "Life" },
  ];
  assert.deepEqual(sampleCourses(rows).map((row) => row.id), ["drivers-ed"]);
});

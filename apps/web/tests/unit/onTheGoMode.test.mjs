import test from "node:test";
import assert from "node:assert/strict";

import {
  DEMO_COURSE_ID,
  ON_THE_GO_DEMO_SECONDS,
  onTheGoExperience,
  sampleCourses,
  timerLabel,
} from "../../app/lib/onTheGoMode.ts";

test("demo mode shows the 10-minute timer and does not enable Sala", () => {
  const demo = onTheGoExperience("demo");
  assert.equal(demo.showTimer, true);
  assert.equal(demo.sampleSeconds, ON_THE_GO_DEMO_SECONDS);
  assert.equal(demo.sampleSeconds, 600);
  assert.equal(demo.salaAgent, false);
  assert.equal(demo.fullCatalog, false);
  assert.equal(demo.showCoursePicker, false);
  assert.equal(timerLabel(600), "10:00");
  assert.equal(timerLabel(65), "1:05");
});

test("full mode has no timer and enables the Sala agent", () => {
  const full = onTheGoExperience("full");
  assert.equal(full.showTimer, false);
  assert.equal(full.sampleSeconds, 0);
  assert.equal(full.salaAgent, true);
  assert.equal(full.fullCatalog, true);
  assert.equal(full.showCoursePicker, true);
});

test("sampleCourses prefers the pinned AI demo course by id", () => {
  const rows = [
    { id: "algebra", title: "Algebra", category: "Math" },
    { id: "drivers-ed", title: "Driver's Education", category: "Safety" },
    { id: DEMO_COURSE_ID, title: "Introduction to Machine Learning", category: "Data Science & AI" },
    { id: "cooking", title: "Cooking", category: "Life" },
  ];
  assert.deepEqual(sampleCourses(rows).map((row) => row.id), [DEMO_COURSE_ID]);
});

test("sampleCourses falls back to any AI/ML/data-science row when the pinned id is missing", () => {
  const rows = [
    { id: "algebra", title: "Algebra", category: "Math" },
    { id: "drivers-ed", title: "Driver's Education", category: "Safety" },
    { id: "audio-neural-networks-explained", title: "Neural Networks Explained", category: "Data Science & AI" },
  ];
  assert.deepEqual(sampleCourses(rows).map((row) => row.id), ["audio-neural-networks-explained"]);
});

test("sampleCourses falls back to drivers-ed when no AI course exists (legacy behavior)", () => {
  const rows = [
    { id: "algebra", title: "Algebra", category: "Math" },
    { id: "drivers-ed", title: "Driver's Education", category: "Safety" },
    { id: "cooking", title: "Cooking", category: "Life" },
  ];
  assert.deepEqual(sampleCourses(rows).map((row) => row.id), ["drivers-ed"]);
});

test("sampleCourses falls back to the first row when nothing matches", () => {
  const rows = [
    { id: "algebra", title: "Algebra", category: "Math" },
    { id: "cooking", title: "Cooking", category: "Life" },
  ];
  assert.deepEqual(sampleCourses(rows).map((row) => row.id), ["algebra"]);
});

test("sampleCourses handles an empty catalog without crashing", () => {
  assert.deepEqual(sampleCourses([]), []);
});

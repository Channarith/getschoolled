import test from "node:test";
import assert from "node:assert/strict";

import {
  DEMO_COURSE_IDS, QuestionLimiter, cleanTitle, curatedRows, matchCourse, neighbourCourse, parseCourseCommand,
  readProgress, resumeSegment, saveProgress, PROGRESS_KEY,
} from "../../app/lib/onTheGoCatalog.ts";
import { PresenceTracker, cameraWanted, CAMERA_PREF_KEY } from "../../app/lib/facePresence.ts";
import { onTheGoExperience } from "../../app/lib/onTheGoMode.ts";

const rows = [
  { id: "audio-intro-to-machine-learning", title: "Intro to Machine Learning (audio)", category: "Technology", duration_min: 5 },
  { id: "audio-the-roman-empire", title: "The Roman Empire (audio)", category: "History", duration_min: 6 },
  { id: "audio-ancient-egypt", title: "Ancient Egypt (audio)", category: "History", duration_min: 6 },
  { id: "audio-the-history-of-cinema", title: "The History of Cinema (audio)", category: "Arts & Culture", duration_min: 5 },
  { id: "audio-cybersecurity-basics", title: "Cybersecurity Basics (audio)", category: "Technology", duration_min: 4 },
];

function memoryStorage(seed = {}) {
  const data = { ...seed };
  return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, data };
}

test("curated list is unique and the default course comes first", () => {
  assert.equal(new Set(DEMO_COURSE_IDS).size, DEMO_COURSE_IDS.length);
  assert.equal(DEMO_COURSE_IDS[0], "audio-intro-to-machine-learning");
  const out = curatedRows([...rows].reverse());
  assert.deepEqual(out.map((r) => r.id), ["audio-intro-to-machine-learning", "audio-cybersecurity-basics", "audio-the-roman-empire", "audio-ancient-egypt", "audio-the-history-of-cinema"]);
  assert.deepEqual(curatedRows([{ id: "not-curated" }]), []);
});

test("demo gets the curated picker unless the flag turns it off", () => {
  assert.equal(onTheGoExperience("demo").curatedPicker, true);
  assert.equal(onTheGoExperience("demo", { curatedPicker: false }).curatedPicker, false);
  assert.equal(onTheGoExperience("full").curatedPicker, false);
});

test("titles lose the (audio) suffix", () => {
  assert.equal(cleanTitle("The Roman Empire (audio)"), "The Roman Empire");
  assert.equal(cleanTitle(""), "");
});

test("matchCourse finds a course from a spoken phrase", () => {
  assert.equal(matchCourse("the roman empire", rows)?.id, "audio-the-roman-empire");
  assert.equal(matchCourse("roman", rows)?.id, "audio-the-roman-empire");
  assert.equal(matchCourse("cinema", rows)?.id, "audio-the-history-of-cinema");
  assert.equal(matchCourse("machine learning", rows)?.id, "audio-intro-to-machine-learning");
  assert.equal(matchCourse("quantum cooking", rows), null);
  assert.equal(matchCourse("", rows), null);
});

test("course voice commands", () => {
  const here = "audio-ancient-egypt";
  assert.deepEqual(parseCourseCommand("play the Roman Empire course", rows, here), { kind: "play", id: "audio-the-roman-empire" });
  assert.deepEqual(parseCourseCommand("Play the roman empire course.", rows, here), { kind: "play", id: "audio-the-roman-empire" });
  assert.deepEqual(parseCourseCommand("switch to cybersecurity", rows, here), { kind: "play", id: "audio-cybersecurity-basics" });
  assert.deepEqual(parseCourseCommand("can you play the history of cinema", rows, here), { kind: "play", id: "audio-the-history-of-cinema" });
  assert.deepEqual(parseCourseCommand("next course", rows, here), { kind: "next" });
  assert.deepEqual(parseCourseCommand("play another course", rows, here), { kind: "next" });
  assert.deepEqual(parseCourseCommand("previous course", rows, here), { kind: "previous" });
  assert.deepEqual(parseCourseCommand("what courses do you have", rows, here), { kind: "list" });
  assert.deepEqual(parseCourseCommand("play the quantum cooking course", rows, here), { kind: "unknown", wanted: "the quantum cooking" });
});

test("playback and question phrases are not course commands", () => {
  for (const text of ["play", "play it again", "play that", "play that again", "play from the start", "play the lesson", "faster", "pause", "what is a denominator", "play faster", "how does inflation work", ""]) {
    assert.equal(parseCourseCommand(text, rows, "x"), null, text);
  }
});

test("neighbourCourse wraps around and handles an unknown current course", () => {
  assert.equal(neighbourCourse(rows, rows[0].id, 1).id, rows[1].id);
  assert.equal(neighbourCourse(rows, rows[rows.length - 1].id, 1).id, rows[0].id);
  assert.equal(neighbourCourse(rows, rows[0].id, -1).id, rows[rows.length - 1].id);
  assert.equal(neighbourCourse(rows, "missing", 1).id, rows[0].id);
  assert.equal(neighbourCourse([], "x", 1), null);
});

test("resume points are remembered per course", () => {
  const st = memoryStorage();
  assert.deepEqual(readProgress(st), { lastCourseId: "", courses: {} });
  saveProgress("a", 3, st, 100);
  saveProgress("b", 7, st, 200);
  const p = readProgress(st);
  assert.equal(p.lastCourseId, "b");
  assert.equal(p.courses.a.seg, 3);
  assert.equal(resumeSegment(p, "a", 10), 3);
  assert.equal(resumeSegment(p, "a", 3), 0, "a saved point past the end restarts the course");
  assert.equal(resumeSegment(p, "zzz", 10), 0);
  assert.equal(resumeSegment(p, "a", 0), 0);
});

test("corrupt or hostile stored progress never throws", () => {
  for (const raw of ["", "{", "null", "[]", '{"courses":null}', '{"courses":{"a":{"seg":-1}}}', '{"courses":{"a":{"seg":"x"}}}', '{"courses":{"a":{"seg":1.5}}}']) {
    const st = memoryStorage({ [PROGRESS_KEY]: raw });
    const p = readProgress(st);
    assert.deepEqual(Object.keys(p.courses), [], raw);
  }
  assert.deepEqual(readProgress(null), { lastCourseId: "", courses: {} });
  saveProgress("a", 1, null);
  saveProgress("", 1, memoryStorage());
  saveProgress("a", -2, memoryStorage());
});

test("only the most recent 60 courses are remembered", () => {
  const st = memoryStorage();
  for (let i = 0; i < 75; i += 1) saveProgress(`c${i}`, 1, st, i);
  const p = readProgress(st);
  assert.equal(Object.keys(p.courses).length, 60);
  assert.ok(p.courses.c74 && !p.courses.c0);
});

test("question limiter: burst limit, then recovery, then session cap", () => {
  let now = 1_000;
  const lim = new QuestionLimiter(3, 5, () => now);
  assert.equal(lim.check().ok, true);
  assert.equal(lim.check().ok, true);
  assert.equal(lim.check().ok, true);
  const blocked = lim.check();
  assert.equal(blocked.ok, false);
  assert.equal(blocked.reason, "rate");
  assert.ok(blocked.retryAfterS >= 1 && blocked.retryAfterS <= 60);
  now += 61_000;
  assert.equal(lim.check().ok, true);
  assert.equal(lim.check().ok, true);
  const capped = lim.check();
  assert.equal(capped.ok, false);
  assert.equal(capped.reason, "session");
  lim.reset();
  assert.equal(lim.check().ok, true);
});

test("presence: a blink does not pause, a real absence does, and coming back resumes", () => {
  const tr = new PresenceTracker(4000, 700);
  let t = 0;
  const step = (present, ms) => { t += ms; return tr.update(present, t); };
  assert.equal(step(true, 250), null);
  assert.equal(step(false, 250), null);       // dropped frame
  assert.equal(step(true, 250), null);        // back before the threshold
  assert.equal(tr.isPresent, true);
  let ev = null;
  for (let i = 0; i < 20 && !ev; i += 1) ev = step(false, 250);
  assert.equal(ev, "away");
  assert.equal(tr.isPresent, false);
  assert.equal(step(false, 250), null, "away is reported once");
  assert.equal(step(true, 250), null);
  assert.equal(step(true, 250), null);
  assert.equal(step(true, 250), null);
  assert.equal(step(true, 250), "back", "700 ms of steady presence");
  assert.equal(tr.isPresent, true);
});

test("presence: flapping readings never reach the threshold", () => {
  const tr = new PresenceTracker(4000, 700);
  let t = 0;
  let events = 0;
  for (let i = 0; i < 200; i += 1) {
    t += 250;
    if (tr.update(i % 3 !== 0, t)) events += 1;   // missing one frame in three
  }
  assert.equal(events, 0);
});

test("camera preference: on by default, off only when the learner chose off", () => {
  assert.equal(cameraWanted(null), true);
  assert.equal(cameraWanted({ getItem: () => null }), true);
  assert.equal(cameraWanted({ getItem: (k) => (k === CAMERA_PREF_KEY ? "off" : null) }), false);
  assert.equal(cameraWanted({ getItem: () => { throw new Error("blocked"); } }), true);
});

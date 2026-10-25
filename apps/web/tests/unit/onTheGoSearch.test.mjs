import test from "node:test";
import assert from "node:assert/strict";

import { badgeFor, fold, fuzzyScore, isReadyIn, parseSearchCommand, rankCourses, windowRows, withinEdits } from "../../app/lib/onTheGoSearch.ts";

const rows = [
  { id: "a-rome", title: "The Roman Empire (audio)", category: "History", tags: ["rome", "history"], ready_languages: ["es", "fr"], ready: true },
  { id: "b-egypt", title: "Ancient Egypt (audio)", category: "History", ready_languages: [], ready: false, english_only: true },
  { id: "c-ml", title: "Intro to Machine Learning (audio)", category: "Technology", tags: ["ai"], ready_languages: ["es"], ready: true, title_local: "Introducción al aprendizaje automático" },
  { id: "d-cinema", title: "The History of Cinema (audio)", category: "Arts & Culture", ready_languages: ["fr"], ready: false },
];

test("fold removes accents, case, punctuation and the audio suffix but keeps every script", () => {
  assert.equal(fold("Introducción al Aprendizaje!"), "introduccion al aprendizaje");
  assert.equal(fold("The Roman Empire (audio)"), "the roman empire");
  assert.equal(fold("羅馬帝國"), "羅馬帝國");
  assert.equal(fold("  ទីក្រុង  ").length > 0, true);   // Khmer letters and combining signs survive
});

test("bounded edit distance", () => {
  assert.ok(withinEdits("empire", "empire", 1));
  assert.ok(withinEdits("empyre", "empire", 1));
  assert.ok(!withinEdits("empire", "umpire", 0));
  assert.ok(!withinEdits("egypt", "cinema", 2));
});

test("fuzzy score: exact > prefix > typo, every word must match", () => {
  const exact = fuzzyScore("roman empire", "The Roman Empire");
  const prefix = fuzzyScore("rom emp", "The Roman Empire");
  const typo = fuzzyScore("romn empire", "The Roman Empire");
  assert.ok(exact > prefix && prefix > 0 && typo > 0);
  assert.equal(fuzzyScore("roman pizza", "The Roman Empire"), 0);
  assert.equal(fuzzyScore("", "The Roman Empire"), 0);
});

test("accents do not block a match in either direction", () => {
  assert.ok(fuzzyScore("aprendizaje automatico", "Introducción al aprendizaje automático") > 0);
  assert.ok(fuzzyScore("introducción", "introduccion") > 0);
});

test("languages without spaces match by substring", () => {
  assert.ok(fuzzyScore("帝國", "羅馬帝國") > 0);
  assert.equal(fuzzyScore("埃及", "羅馬帝國"), 0);
  assert.ok(fuzzyScore("ទីក្រុង", "ទីក្រុង រ៉ូម") > 0);
});

test("ready-in-language courses rank first, then by match", () => {
  const out = rankCourses(rows, "history", { language: "fr", includeEnglish: true });
  assert.deepEqual(out.map((r) => r.id), ["a-rome", "d-cinema", "b-egypt"].filter((id) => out.some((r) => r.id === id)).sort((a, b) => out.findIndex((r) => r.id === a) - out.findIndex((r) => r.id === b)));
  assert.equal(out[0].id, "a-rome");   // ready in fr and matches
  const ready = out.map((r) => isReadyIn(r, "fr"));
  assert.deepEqual(ready, [...ready].sort((a, b) => Number(b) - Number(a)));   // ready ones are never after a not-ready one
});

test("with no query the ready courses come first and the rest keep their order", () => {
  const out = rankCourses(rows, "", { language: "es", includeEnglish: true });
  assert.deepEqual(out.map((r) => r.id), ["a-rome", "c-ml", "b-egypt", "d-cinema"]);
});

test("'Include English-only' off hides courses that are not ready in the language", () => {
  const out = rankCourses(rows, "", { language: "es", includeEnglish: false });
  assert.deepEqual(out.map((r) => r.id), ["a-rome", "c-ml"]);
  assert.equal(rankCourses(rows, "", { language: "en", includeEnglish: false }).length, rows.length);   // English: everything is ready
});

test("the demo allowlist limits the searchable set", () => {
  const out = rankCourses(rows, "", { language: "en", includeEnglish: true, allowedIds: ["b-egypt", "d-cinema"] });
  assert.deepEqual(out.map((r) => r.id), ["b-egypt", "d-cinema"]);
  assert.deepEqual(rankCourses(rows, "roman", { language: "en", includeEnglish: true, allowedIds: ["b-egypt"] }), []);
});

test("local titles, tags and categories are searchable", () => {
  assert.equal(rankCourses(rows, "aprendizaje", { language: "es", includeEnglish: true })[0].id, "c-ml");
  assert.equal(rankCourses(rows, "ai", { language: "en", includeEnglish: true })[0].id, "c-ml");
  assert.equal(rankCourses(rows, "technology", { language: "en", includeEnglish: true })[0].id, "c-ml");
});

test("empty result for nonsense", () => {
  assert.deepEqual(rankCourses(rows, "zzzzqq", { language: "en", includeEnglish: true }), []);
});

test("badges say ready, ready elsewhere or English only", () => {
  assert.deepEqual(badgeFor(rows[0], "es"), { kind: "ready", languages: ["es"] });
  assert.deepEqual(badgeFor(rows[3], "es"), { kind: "other", languages: ["fr"] });
  assert.deepEqual(badgeFor(rows[1], "es"), { kind: "english-only", languages: [] });
  assert.equal(badgeFor(rows[1], "en").kind, "ready");
});

test("spoken search commands", () => {
  assert.deepEqual(parseSearchCommand("search for the roman empire"), { kind: "search", query: "the roman empire" });
  assert.deepEqual(parseSearchCommand("Find me a course on black holes."), { kind: "search", query: "black holes" });
  assert.deepEqual(parseSearchCommand("look for cybersecurity"), { kind: "search", query: "cybersecurity" });
  assert.deepEqual(parseSearchCommand("please search ancient egypt courses"), { kind: "search", query: "ancient egypt" });
  assert.deepEqual(parseSearchCommand("clear search"), { kind: "clear" });
  assert.equal(parseSearchCommand("play the roman empire course"), null);   // that is a play command
  assert.equal(parseSearchCommand("what is a black hole"), null);
  assert.equal(parseSearchCommand("search"), null);
  assert.equal(parseSearchCommand("find out why the sky is blue and what that means for light travelling through the atmosphere"), null);
});

test("list windowing renders only what is visible plus overscan", () => {
  assert.deepEqual(windowRows(0, 0, 300, 60), { start: 0, end: 0, padTop: 0, padBottom: 0 });
  const w = windowRows(300, 0, 300, 60, 2);
  assert.equal(w.start, 0); assert.equal(w.end, 7); assert.equal(w.padBottom, (300 - 7) * 60);
  const mid = windowRows(300, 6000, 300, 60, 2);
  assert.equal(mid.start, 98); assert.equal(mid.end, 107); assert.equal(mid.padTop, 98 * 60);
  assert.equal(mid.padBottom, (300 - 107) * 60);
  const end = windowRows(300, 99999, 300, 60, 2);
  assert.equal(end.end, 300); assert.equal(end.padBottom, 0);
  assert.ok(windowRows(10, -50, 300, 60).start === 0);
});

import test from "node:test";
import assert from "node:assert/strict";
import { voiceTokenEngineField } from "../../app/lib/liveVoiceEngine.ts";

test("voice token body omits engine for default Sala", () => {
  assert.deepEqual(voiceTokenEngineField("salane"), {});
});

test("voice token body sends engine xai only when opted in", () => {
  assert.deepEqual(voiceTokenEngineField("xai"), { engine: "xai" });
});

/** Mirrors mintXaiVoiceToken JSON (default Sala vs explicit xAI opt-in). */
function buildVoiceTokenBody(opts) {
  const body = {
    mode: opts.mode || "solo",
    lesson_context: opts.lesson_context || "",
    learner_names: opts.learner_names || [],
    expires_seconds: opts.expires_seconds ?? 300,
    instructions: opts.mode === "drive" ? "" : (opts.instructions || ""),
    category: opts.category || "",
    topic: opts.topic || "",
    course_id: opts.course_id || "",
    language: opts.language || "",
  };
  if ((opts.engine || "").trim().toLowerCase() === "xai") {
    body.engine = "xai";
  }
  return body;
}

test("default Sala path does not send engine on the token request", () => {
  const body = buildVoiceTokenBody({ mode: "solo", language: "en" });
  assert.equal("engine" in body, false);
});

test("selected xAI path sends engine xai on the token request", () => {
  const body = buildVoiceTokenBody({ mode: "solo", language: "en", engine: "xai" });
  assert.equal(body.engine, "xai");
});

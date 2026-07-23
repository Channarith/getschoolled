import { expect, test } from "@playwright/test";

import { SpeechChunker, StreamingVoice, type Playable } from "../../app/lib/voicePipeline";
import {
  createVoicePauseSubmitter,
  normalizeVoicePauseSubmitMs,
} from "../../app/lib/voiceCommands";

/**
 * Latency-critical chunking for the real-time voice pipeline: the FIRST chunk
 * must be tiny (fast time-to-first-audio), subsequent chunks phrase-sized.
 */
test.describe("SpeechChunker (real-time voice)", () => {
  test("emits a tiny first chunk then phrase-sized chunks", () => {
    const ch = new SpeechChunker({ firstChunkWords: 3, minWords: 4, maxWords: 9 });
    const chunks: string[] = [];
    // Stream tokens roughly as an LLM would.
    for (const tok of ["Photo", "synthesis ", "is ", "the process ", "by which ", "plants ", "make ", "food, ", "using ", "sunlight ", "and water."]) {
      chunks.push(...ch.feed(tok));
    }
    const tail = ch.flush();
    if (tail) chunks.push(tail);

    // First chunk is ~3 words (low latency), not the whole sentence.
    expect(chunks[0].split(/\s+/).length).toBeLessThanOrEqual(3);
    expect(chunks.length).toBeGreaterThan(1);
    // Nothing is lost: chunks concatenate back to the full text.
    expect(chunks.join(" ").replace(/\s+/g, " ").trim())
      .toBe("Photosynthesis is the process by which plants make food, using sunlight and water.");
  });

  test("breaks on punctuation once past minWords", () => {
    const ch = new SpeechChunker({ firstChunkWords: 2, minWords: 3, maxWords: 12 });
    const out = ch.feed("Yes indeed. That is right, absolutely.");
    const tail = ch.flush();
    if (tail) out.push(tail);
    // First tiny chunk, then a comma/period phrase break rather than one blob.
    expect(out.length).toBeGreaterThanOrEqual(2);
    expect(out.some((c) => c.endsWith(".") || c.endsWith(","))).toBe(true);
  });

  test("caps chunk size when there is no punctuation", () => {
    const ch = new SpeechChunker({ firstChunkWords: 2, minWords: 3, maxWords: 5 });
    const words = "one two three four five six seven eight nine ten".split(" ");
    const out: string[] = [];
    for (const w of words) out.push(...ch.feed(w + " "));
    // With a maxWords cap of 5 and no punctuation, we must have emitted mid-stream.
    expect(out.length).toBeGreaterThanOrEqual(2);
  });
});

test.describe("StreamingVoice ordering", () => {
  test("plays chunks strictly in order even if later audio is ready first", async () => {
    const played: string[] = [];
    // synth resolves out of order: 'B' ready fast, 'A' slow — playback must be A,B.
    const synth = (t: string): Promise<Playable> => {
      const delay = t.startsWith("A") ? 40 : 0;
      return new Promise((resolve) =>
        setTimeout(() => resolve({
          play: () => { played.push(t); return Promise.resolve(); },
          cancel: () => {},
        }), delay));
    };
    const v = new StreamingVoice(synth);
    v.enqueue("A first");
    v.enqueue("B second");
    await v.drained();
    expect(played).toEqual(["A first", "B second"]);
  });
});

test.describe("Voice pause auto-submit", () => {
  test("normalizeVoicePauseSubmitMs clamps to 500–15000", () => {
    expect(normalizeVoicePauseSubmitMs(4500)).toBe(4500);
    expect(normalizeVoicePauseSubmitMs(100)).toBe(500);
    expect(normalizeVoicePauseSubmitMs(99999)).toBe(15000);
    expect(normalizeVoicePauseSubmitMs("nope", 4500)).toBe(4500);
  });

  test("createVoicePauseSubmitter debounces then submits once", async () => {
    const submitted: string[] = [];
    const submitter = createVoicePauseSubmitter(50, (text) => submitted.push(text));
    submitter.updateTranscript("hello");
    await new Promise((r) => setTimeout(r, 30));
    expect(submitted).toEqual([]);
    await new Promise((r) => setTimeout(r, 30));
    expect(submitted).toEqual(["hello"]);
    submitter.updateTranscript("again");
    await new Promise((r) => setTimeout(r, 80));
    expect(submitted).toEqual(["hello"]);
  });
});

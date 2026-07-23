/**
 * U-VA-1 — wake-word detection + stripping (QA V&V plan, Mobile dimension).
 *
 * The "Hey Sala" assistant gates hands-free control while driving. False
 * positives ("salad") hijack playback; false negatives lose the command. These
 * pin the current grammar, including the known R3 defect where a question ABOUT
 * Sala gets the subject stripped.
 */

import { hasWakeWord, normalizeVoicePauseSubmitMs, stripWakeWords } from "../voiceAssistant";

describe("hasWakeWord", () => {
  test.each([
    ["hey sala", true],
    ["Hey Sala, what's next", true],
    ["sala pause", true],
    ["salareen play", true],
    ["can you ask sala", true],
  ])("%s -> %s (positive)", (input, expected) => {
    expect(hasWakeWord(input)).toBe(expected);
  });

  test.each([
    ["salad recipe", false],
    ["salamander facts", false],
    ["what is the weather", false],
    ["", false],
  ])("%s -> %s (negative, word-boundary guarded)", (input, expected) => {
    expect(hasWakeWord(input)).toBe(expected);
  });
});

describe("stripWakeWords", () => {
  test("removes a leading wake phrase", () => {
    expect(stripWakeWords("hey sala what is generative AI")).toBe("what is generative AI");
  });

  test("removes the bare wake word", () => {
    expect(stripWakeWords("sala skip to the next segment")).toBe("skip to the next segment");
  });

  test("removes 'salareen' anywhere", () => {
    expect(stripWakeWords("ask salareen to resume")).toBe("ask  to resume".trim());
  });

  test("leaves non-wake lookalikes intact", () => {
    expect(stripWakeWords("salad recipe please")).toBe("salad recipe please");
  });

  // R3 known defect (pinned): a question whose SUBJECT is Sala loses the subject.
  // When the localization/grammar fix lands, flip this to the corrected value.
  test("PINNED DEFECT: strips Sala even when it is the question subject", () => {
    expect(stripWakeWords("who is sala")).toBe("who is");
  });
});

describe("normalizeVoicePauseSubmitMs", () => {
  test("defaults to 4.5 seconds", () => {
    expect(normalizeVoicePauseSubmitMs(undefined)).toBe(4500);
    expect(normalizeVoicePauseSubmitMs("nope")).toBe(4500);
  });

  test("accepts admin-tuned values within bounds", () => {
    expect(normalizeVoicePauseSubmitMs(3000)).toBe(3000);
    expect(normalizeVoicePauseSubmitMs("6000")).toBe(6000);
  });

  test("clamps extreme values", () => {
    expect(normalizeVoicePauseSubmitMs(50)).toBe(500);
    expect(normalizeVoicePauseSubmitMs(60000)).toBe(15000);
  });
});

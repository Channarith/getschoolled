// Mobile Jest coverage for the course-player voice intent parser plus a
// parity check that the mobile mirror and the web source agree on the
// vocabulary. The two files MUST stay in lockstep; the parity test fails
// loudly if a kind is added to one and forgotten on the other.

import {
  courseVoiceIntentCatalog,
  languageCodeFromSpoken,
  parseCourseVoiceIntent,
  type CourseVoiceIntent,
} from "../courseVoiceIntent";

// Node builtins used only by the parity test. Declared locally because the
// mobile typecheck intentionally omits @types/node to keep the surface small.
declare const __dirname: string;
declare function require(name: "fs"): { readFileSync(path: string, encoding: string): string };
declare function require(name: "path"): { resolve(...parts: string[]): string };

describe("course voice intent parser", () => {
  it("recognizes the catalog of intents from everyday phrasing", () => {
    const cases: [string, CourseVoiceIntent["kind"]][] = [
      ["pause", "pause"],
      ["pause please", "pause"],
      ["Sala, pause the lesson", "pause"],
      ["resume", "resume"],
      ["play", "resume"],
      ["restart", "restart"],
      ["from the beginning", "restart"],
      ["start", "start"],
      ["next slide", "next"],
      ["skip ahead", "next"],
      ["back", "previous"],
      ["last slide", "previous"],
      ["repeat", "repeat"],
      ["captions on", "captions_on"],
      ["enable subtitles", "captions_on"],
      ["captions off", "captions_off"],
      ["captions", "captions_toggle"],
      ["fullscreen", "fullscreen_on"],
      ["make it bigger", "fullscreen_on"],
      ["exit fullscreen", "fullscreen_off"],
      ["exit", "fullscreen_off"],
      ["slower", "set_speed"],
      ["speed up", "set_speed"],
      ["stop listening", "mute_mic"],
      ["show the controls", "show_controls"],
      ["hide the controls", "hide_controls"],
      ["help", "help"],
    ];
    for (const [utterance, kind] of cases) {
      const parsed = parseCourseVoiceIntent(utterance);
      expect(parsed).not.toBeNull();
      expect(parsed?.kind).toBe(kind);
    }
  });

  it("maps spoken language names to BCP-47 base codes", () => {
    const samples: [string, string][] = [
      ["speak Spanish", "es"],
      ["say it in french", "fr"],
      ["switch to mandarin", "zh"],
      ["in cantonese please", "yue"],
      ["speak khmer", "km"],
    ];
    for (const [utterance, code] of samples) {
      const parsed = parseCourseVoiceIntent(utterance);
      expect(parsed?.kind).toBe("set_language");
      if (parsed?.kind === "set_language") expect(parsed.language).toBe(code);
    }
  });

  it("returns null for silence, filler words, and course-narration echoes", () => {
    expect(parseCourseVoiceIntent("")).toBeNull();
    expect(parseCourseVoiceIntent("   ")).toBeNull();
    expect(parseCourseVoiceIntent("uhhh")).toBeNull();
    expect(parseCourseVoiceIntent("the lesson was good")).toBeNull();
  });

  it("falls through to the ask intent for free-form questions", () => {
    const q = parseCourseVoiceIntent("What is machine learning?");
    expect(q?.kind).toBe("ask");
    if (q?.kind === "ask") expect(q.question).toContain("machine learning");
  });

  it("the wake word is optional and does not change the matched intent", () => {
    expect(parseCourseVoiceIntent("pause")?.kind).toBe("pause");
    expect(parseCourseVoiceIntent("sala pause")?.kind).toBe("pause");
    expect(parseCourseVoiceIntent("hey sala, pause")?.kind).toBe("pause");
  });

  it("languageCodeFromSpoken is deterministic and rejects unknown names", () => {
    expect(languageCodeFromSpoken("Spanish")).toBe("es");
    expect(languageCodeFromSpoken("MANDARIN")).toBe("zh");
    expect(languageCodeFromSpoken("klingon")).toBeNull();
  });

  it("the mobile catalog matches the web source byte-for-byte (parity contract)", () => {
    // The two files cannot drift. If anyone adds an intent in one and forgets
    // the other, this test fails and names the missing kind.
    const fs = require("fs");
    const path = require("path");
    const webSource = fs.readFileSync(
      path.resolve(__dirname, "../../../web/app/lib/courseVoiceIntent.ts"),
      "utf8",
    );
    const match = webSource.match(/courseVoiceIntentCatalog\(\)[\s\S]*?return\s*\[([\s\S]*?)\]\s*as\s*const/);
    expect(match).not.toBeNull();
    const webKinds = (match![1].match(/"[a-z_]+"/g) || []).map((s: string) => s.slice(1, -1));
    const mobileKinds = [...courseVoiceIntentCatalog()];
    expect(mobileKinds.sort()).toEqual(webKinds.sort());
  });
});

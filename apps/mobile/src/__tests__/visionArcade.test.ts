import { visionGameIds, visionLabPath, VISION_ARCADE } from "../visionArcade";

// __dirname and the Node builtins used in the one source-reflection test
// below are injected by Jest's CommonJS runtime. The mobile typecheck config
// intentionally omits @types/node; declare only the exact surface we use.
declare const __dirname: string;
declare function require(name: "fs"): { readFileSync(path: string, encoding: string): string };
declare function require(name: "path"): { resolve(...parts: string[]): string };

describe("vision arcade", () => {
  it("lists every webcam lab game", () => {
    const ids = visionGameIds();
    expect(ids).toHaveLength(43);
    expect(new Set(ids).size).toBe(ids.length);
    expect(VISION_ARCADE.map((section) => section.id)).toEqual(["featured", "learn", "listen", "sing", "face", "move"]);
    // Pop Quiz Toss is the featured first game, in the same order as the lab menu.
    expect(ids[0]).toBe("pop-quiz-toss");
    expect(VISION_ARCADE[0].games.map((game) => game.id)).toEqual(["pop-quiz-toss"]);
    expect(ids).toContain("trace-letter");
    expect(ids).toContain("pop-quiz-toss");
    expect(ids).toContain("spell-aloud");
    expect(ids).toContain("karaoke");
    expect(ids).toContain("rainbow-reach");
    expect(ids).toContain("mirror-hall");
    expect(ids).toContain("ninja-weave");
    expect(ids[ids.indexOf("popcorn") + 1]).toBe("mirror-hall");
    expect(ids[ids.indexOf("mirror-hall") + 1]).toBe("ninja-weave");
  });

  it("opens the lab in the app, with a game when one is chosen", () => {
    expect(visionLabPath()).toBe("/children-lab?embed=mobile");
    expect(visionLabPath("wink")).toBe("/children-lab?embed=mobile&game=wink");
    expect(visionLabPath("pop-quiz-toss")).toBe("/children-lab?embed=mobile&game=pop-quiz-toss");
    expect(visionLabPath("pop-quiz-toss", "child")).toBe("/children-lab?embed=mobile&game=pop-quiz-toss&age=child");
    // Older app builds still ask for the old id; the lab maps it to the new game.
    expect(visionLabPath("math-toss")).toBe("/children-lab?embed=mobile&game=math-toss");
  });

  it("defaults the arcade age band to the younger-safer value until the profile loads", () => {
    // App.tsx stores arcadeAgeBand so Pop Quiz Toss cannot show a teen or adult question to a
    // 4-6 learner during the brief async profile fetch. If this default
    // changes, review child-safety before shipping.
    const fs = require("fs");
    const path = require("path");
    const appSource = fs.readFileSync(path.resolve(__dirname, "../../App.tsx"), "utf8");
    expect(appSource).toContain('useState("4-6")');
    expect(appSource).not.toContain('setArcadeAgeBand("")');
  });
});
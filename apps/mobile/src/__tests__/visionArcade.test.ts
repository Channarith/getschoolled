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
    expect(ids).toHaveLength(41);
    expect(new Set(ids).size).toBe(ids.length);
    expect(VISION_ARCADE.map((section) => section.id)).toEqual(["learn", "listen", "sing", "face", "move"]);
    expect(ids).toContain("trace-letter");
    expect(ids).toContain("math-toss");
    expect(ids).toContain("spell-aloud");
    expect(ids).toContain("karaoke");
    expect(ids).toContain("rainbow-reach");
  });

  it("opens the lab in the app, with a game when one is chosen", () => {
    expect(visionLabPath()).toBe("/children-lab?embed=mobile");
    expect(visionLabPath("wink")).toBe("/children-lab?embed=mobile&game=wink");
    expect(visionLabPath("math-toss")).toBe("/children-lab?embed=mobile&game=math-toss");
    expect(visionLabPath("math-toss", "child")).toBe("/children-lab?embed=mobile&game=math-toss&age=child");
  });

  it("defaults the arcade age band to the younger-safer value until the profile loads", () => {
    // App.tsx stores arcadeAgeBand so Math Toss cannot show multiplication to a
    // 4-6 learner during the brief async profile fetch. If this default
    // changes, review child-safety before shipping.
    const fs = require("fs");
    const path = require("path");
    const appSource = fs.readFileSync(path.resolve(__dirname, "../../App.tsx"), "utf8");
    expect(appSource).toContain('useState("4-6")');
    expect(appSource).not.toContain('setArcadeAgeBand("")');
  });
});
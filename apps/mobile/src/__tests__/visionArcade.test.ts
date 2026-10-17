import { visionGameIds, visionLabPath, VISION_ARCADE } from "../visionArcade";

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
});
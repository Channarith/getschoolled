import { visionGameIds, visionLabPath, VISION_ARCADE } from "../visionArcade";

describe("vision arcade", () => {
  it("lists every webcam lab game", () => {
    const ids = visionGameIds();
    expect(ids).toHaveLength(39);
    expect(new Set(ids).size).toBe(ids.length);
    expect(VISION_ARCADE.map((section) => section.id)).toEqual(["learn", "listen", "face", "move"]);
    expect(ids).toContain("trace-letter");
    expect(ids).toContain("spell-aloud");
    expect(ids).toContain("rainbow-reach");
  });

  it("opens the lab in the app, with a game when one is chosen", () => {
    expect(visionLabPath()).toBe("/children-lab?embed=mobile");
    expect(visionLabPath("wink")).toBe("/children-lab?embed=mobile&game=wink");
  });
});
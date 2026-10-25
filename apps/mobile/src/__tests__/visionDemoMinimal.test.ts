import { readFileSync } from "fs";
import { join } from "path";

const screen = readFileSync(join(__dirname, "..", "screens", "DemoWebScreen.tsx"), "utf8");

describe("Vision Play on the phone is just the game", () => {
  it("hides the native header bar for vision demos (Back, title, Camera check live in the game's widget menu)", () => {
    expect(screen).toContain("const hideBar = (cleanCourse || (isVisionDemo && !checking)) && !error;");
    expect(screen).toContain("{hideBar ? null : <View style={styles.bar}");
  });

  it("keeps a way back from the camera check page and from errors", () => {
    // The bar returns while the diagnostics page is open and when an error screen is showing.
    expect(screen).toContain("!checking)) && !error");
    expect(screen).toContain('message.type === "salareen-camera-check"');
    expect(screen).toContain('message.type === "salareen-exit"');
  });
});

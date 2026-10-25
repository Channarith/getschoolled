export {};   // makes this a module, so the declarations below stay local to this file

// Node builtins, declared locally because the mobile typecheck intentionally omits @types/node.
declare const __dirname: string;
declare function require(name: "fs"): { readFileSync(path: string, encoding: string): string };
declare function require(name: "path"): { resolve(...parts: string[]): string };

const fs = require("fs");
const path = require("path");
const screen = fs.readFileSync(path.resolve(__dirname, "..", "screens", "DemoWebScreen.tsx"), "utf8");

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

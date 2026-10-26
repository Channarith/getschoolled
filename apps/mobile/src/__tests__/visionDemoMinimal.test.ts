export {};   // makes this a module, so the declarations below stay local to this file

// Node builtins, declared locally because the mobile typecheck intentionally omits @types/node.
declare const __dirname: string;
declare function require(name: "fs"): { readFileSync(path: string, encoding: string): string };
declare function require(name: "path"): { resolve(...parts: string[]): string };

const fs = require("fs");
const path = require("path");
const screen = fs.readFileSync(path.resolve(__dirname, "..", "screens", "DemoWebScreen.tsx"), "utf8");

describe("Vision Play on the phone is just the game", () => {
  it("hides the native header bar so the webcam fills the screen", () => {
    expect(screen).toContain("const immersiveWeb = (cleanCourse || isVisionDemo || audioOnly || studioCourse) && !error;");
    expect(screen).toContain("const hideBar = immersiveWeb;");
    expect(screen).toContain("{hideBar ? null : <View style={styles.bar}");
  });

  it("keeps a small corner control for back and camera check, including while the check is open", () => {
    expect(screen).toContain('testID="demo-web-back"');
    expect(screen).toContain('testID="demo-camera-check-toggle"');
    expect(screen).toContain("CornerChip");
    expect(screen).toContain('message.type === "salareen-camera-check"');
    expect(screen).toContain('message.type === "salareen-exit"');
  });
});

export {};

declare const __dirname: string;
declare function require(name: string): any;

const fs = require("fs");
const path = require("path");

const appSource = fs.readFileSync(path.resolve(__dirname, "../../App.tsx"), "utf8");

describe("App navigation source guards", () => {
  it("hides main tabs while a kids lesson overlay is active", () => {
    const mainTabsStart = appSource.indexOf("const mainTabsVisible");
    const mainTabsBlock = appSource.slice(mainTabsStart, mainTabsStart + 350);
    expect(mainTabsBlock).toContain("!kidsLessonId");
  });

  it("clears kids lesson state on sign-out and tab changes", () => {
    const signOutStart = appSource.indexOf("authenticated\" && authStatus === \"unauthenticated");
    const signOutBlock = appSource.slice(signOutStart, signOutStart + 900);
    expect(signOutBlock).toContain("setKidsLessonId(null)");

    const tabChangeStart = appSource.indexOf("const onTabChange");
    const tabChangeBlock = appSource.slice(tabChangeStart, tabChangeStart + 900);
    expect(tabChangeBlock).toContain("setKidsLessonId(null)");
  });
});

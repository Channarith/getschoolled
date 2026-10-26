import { HIDDEN_ON_THE_GO_DEMO, PUBLIC_DEMOS, appStateScript, publicDemoUrl } from "../publicDemos";

describe("public demos", () => {
  test("matches the website demo pages", () => {
    expect(PUBLIC_DEMOS.map((demo) => demo.path)).toEqual([
      "/studio?access=sample&course=drivers-ed&demo=1&embed=mobile",
      "/children-lab?embed=mobile&demo=1",
    ]);
  });

  test("keeps the audio demo out of the picker but reachable", () => {
    expect(PUBLIC_DEMOS.some((demo) => demo.id === "on-the-go")).toBe(false);
    expect(HIDDEN_ON_THE_GO_DEMO.path).toBe("/demo/on-the-go");
  });

  test("builds an absolute URL from the web app origin", () => {
    expect(publicDemoUrl("https://www.salareen.com/", "/children-lab?embed=mobile")).toBe(
      "https://www.salareen.com/children-lab?embed=mobile",
    );
  });

  test("does not inject CSS over the game's own minimal layout", () => {
    expect(require("../publicDemos").childrenLabTouchScript).toBeUndefined();
  });

  test("tells the lesson page when the app leaves and returns", () => {
    expect(appStateScript("background")).toContain('"salareen-app-state",{detail:{state:"background"}}');
    expect(appStateScript("active")).toContain('state:"active"');
    expect(appStateScript("active")).toContain('type:"salareen-app-state",state:"active"');
    expect(appStateScript("unknown\"evil")).toContain('state:"active"');
    expect(appStateScript("active").trim().endsWith("true;")).toBe(true);
  });
});

describe("isPageHttpError", () => {
  const page = "https://www.salareen.com/children-lab?embed=mobile&game=pop-quiz-toss";

  it("treats an error for the page itself as fatal", () => {
    expect(require("../publicDemos").isPageHttpError("https://www.salareen.com/children-lab?embed=mobile", page)).toBe(true);
    expect(require("../publicDemos").isPageHttpError(undefined, page)).toBe(true);
  });

  it("ignores a failing asset so the lab stays on screen", () => {
    const { isPageHttpError } = require("../publicDemos");
    expect(isPageHttpError("https://www.salareen.com/vendor/vision/tasks-vision.mjs", page)).toBe(false);
    expect(isPageHttpError("https://www.salareen.com/favicon.ico", page)).toBe(false);
  });
});

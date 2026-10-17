import { PUBLIC_DEMOS, appStateScript, childrenLabTouchScript, publicDemoUrl } from "../publicDemos";

describe("public demos", () => {
  test("matches the website demo pages", () => {
    expect(PUBLIC_DEMOS.map((demo) => demo.path)).toEqual([
      "/studio?access=sample&course=drivers-ed&embed=mobile",
      "/demo/on-the-go",
      "/children-lab?embed=mobile",
    ]);
  });

  test("builds an absolute URL from the web app origin", () => {
    expect(publicDemoUrl("https://www.salareen.com/", "/children-lab?embed=mobile")).toBe(
      "https://www.salareen.com/children-lab?embed=mobile",
    );
  });

  test("pins the vision-lab touch switch on the screen", () => {
    const script = childrenLabTouchScript();
    expect(script).toContain("touch-mode");
    expect(script).toContain("position:fixed");
    expect(script).toContain("vision-readout");
    expect(script).toContain("#countdown:not(.hidden)");
  });

  test("tells the lesson page when the app leaves and returns", () => {
    expect(appStateScript("background")).toContain('"salareen-app-state",{detail:{state:"background"}}');
    expect(appStateScript("active")).toContain('state:"active"');
    expect(appStateScript("active")).toContain('type:"salareen-app-state",state:"active"');
    expect(appStateScript("unknown\"evil")).toContain('state:"active"');
    expect(appStateScript("active").trim().endsWith("true;")).toBe(true);
  });
});

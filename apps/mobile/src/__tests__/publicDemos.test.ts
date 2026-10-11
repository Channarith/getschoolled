import { PUBLIC_DEMOS, childrenLabTouchScript, publicDemoUrl } from "../publicDemos";

describe("public demos", () => {
  test("matches the website demo pages", () => {
    expect(PUBLIC_DEMOS.map((demo) => demo.path)).toEqual([
      "/studio?access=sample&course=drivers-ed&embed=mobile",
      "/studio?access=sample&course=drivers-ed&presentation=audio&embed=mobile",
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
});

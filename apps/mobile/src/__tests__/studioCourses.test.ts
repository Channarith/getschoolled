import { studioCourseFromLink, studioCoursePath } from "../studioCourses";

describe("studio courses", () => {
  it("builds a studio url that carries no entitlement claims", () => {
    const path = studioCoursePath("drivers-ed", "full", { accountId: "acct-1" });
    expect(path).toContain("access=full");
    expect(path).toContain("course=drivers-ed");
    expect(path).toContain("embed=mobile");
    expect(path).not.toMatch(/admin=|enrollment=|registered=/);
  });

  it("builds the audio demo url", () => {
    expect(studioCoursePath("drivers-ed", "sample", { presentation: "audio" })).toContain("presentation=audio");
  });

  it("recognizes catalog links and ignores other courses", () => {
    expect(studioCourseFromLink("course_studio:drivers-ed", "/learn/drivers-ed")).toBe("drivers-ed");
    expect(studioCourseFromLink("food-safety")).toBe("food-safety");
    expect(studioCourseFromLink("intro-to-fractions", "/drive")).toBeNull();
  });
});

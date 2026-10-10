import { fullClassAllowed, studioCourseFromLink, studioCoursePath } from "../studioCourses";

describe("studio courses", () => {
  it("builds a full mobile studio url for an admin", () => {
    const path = studioCoursePath("drivers-ed", "full", { accountId: "acct-1", isAdmin: true });
    expect(path).toContain("access=full");
    expect(path).toContain("course=drivers-ed");
    expect(path).toContain("embed=mobile");
    expect(path).toContain("admin=1");
    expect(path).not.toContain("enrollment=paid");
  });

  it("builds the paid food safety url and the audio demo", () => {
    expect(studioCoursePath("food-safety", "full", { accountId: "acct-1" })).toContain("enrollment=paid");
    expect(studioCoursePath("drivers-ed", "sample", { presentation: "audio" })).toContain("presentation=audio");
  });

  it("recognizes catalog links and ignores other courses", () => {
    expect(studioCourseFromLink("course_studio:drivers-ed", "/learn/drivers-ed")).toBe("drivers-ed");
    expect(studioCourseFromLink("food-safety")).toBe("food-safety");
    expect(studioCourseFromLink("intro-to-fractions", "/drive")).toBeNull();
    expect(fullClassAllowed(true, "paid", false)).toBe(true);
    expect(fullClassAllowed(true, "enrolled", false)).toBe(false);
    expect(fullClassAllowed(false, "", true)).toBe(true);
  });
});
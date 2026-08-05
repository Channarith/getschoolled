/**
 * Kids catalog cards must open the thing they point at.
 *
 * The Kids rails listed the picture adventures and the arcade games, but every
 * tap went to Drive Mode — which has no audio course for either — so the
 * headline kids content was unreachable on mobile. This pins the routing rule
 * that App.openCatalogItem implements: route on deep_link, fall back to Drive.
 */

import { routeForCatalogItem } from "../catalogRouting";

describe("kids catalog deep-link routing", () => {
  it("opens a picture adventure in the kids lesson player", () => {
    expect(
      routeForCatalogItem("kids-abc-adventures", "/kids/learn?course=kids-abc-adventures"),
    ).toEqual({ kind: "kidsLesson", courseId: "kids-abc-adventures" });
  });

  it("opens a learning game in the arcade, not Drive Mode", () => {
    expect(routeForCatalogItem("biology", "/arcade?subject=biology")).toEqual({
      kind: "game",
      subject: "biology",
    });
  });

  it("still sends ordinary audio courses to Drive Mode", () => {
    expect(routeForCatalogItem("audio-course-1", undefined)).toEqual({
      kind: "drive",
      courseId: "audio-course-1",
    });
    expect(routeForCatalogItem("audio-course-1", "")).toEqual({
      kind: "drive",
      courseId: "audio-course-1",
    });
  });

  it("decodes escaped ids and ignores extra query params", () => {
    expect(
      routeForCatalogItem("x", "/kids/learn?course=kids%2Dabc%2Dadventures&from=rail"),
    ).toEqual({ kind: "kidsLesson", courseId: "kids-abc-adventures" });
    expect(routeForCatalogItem("x", "/arcade?subject=data%20science&mode=quiz")).toEqual({
      kind: "game",
      subject: "data science",
    });
  });

  it("falls back to Drive for a deep link it does not understand", () => {
    expect(routeForCatalogItem("c1", "/watch?course=c1")).toEqual({
      kind: "drive",
      courseId: "c1",
    });
  });
});

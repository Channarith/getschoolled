import {
  gridColumnsFor,
  liveRoomSeatSize,
  railCardWidth,
  widthClassFor,
} from "../layout/breakpoints";

describe("widthClassFor", () => {
  it("uses compact below 600 logical px", () => {
    expect(widthClassFor(599)).toBe("compact");
    expect(widthClassFor(320)).toBe("compact");
  });

  it("uses medium from 600 through 839", () => {
    expect(widthClassFor(600)).toBe("medium");
    expect(widthClassFor(839)).toBe("medium");
  });

  it("uses expanded from 840 upward", () => {
    expect(widthClassFor(840)).toBe("expanded");
    expect(widthClassFor(1280)).toBe("expanded");
  });
});

describe("gridColumnsFor", () => {
  it("maps width classes to column counts", () => {
    expect(gridColumnsFor("compact")).toBe(1);
    expect(gridColumnsFor("medium")).toBe(2);
    expect(gridColumnsFor("expanded")).toBe(3);
  });
});

describe("adaptive sizing helpers", () => {
  it("grows rail cards and live-room seats with width class", () => {
    expect(railCardWidth("compact")).toBeLessThan(railCardWidth("medium"));
    expect(railCardWidth("medium")).toBeLessThan(railCardWidth("expanded"));
    expect(liveRoomSeatSize("compact").width).toBeLessThan(liveRoomSeatSize("expanded").width);
  });
});

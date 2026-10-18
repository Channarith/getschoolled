/**
 * MascotActor render smoke + pose-rules unit test.
 *
 * Two layers of coverage:
 *
 *   1. `poseForAge` is pure — age wheel values must map to a stable
 *      ``child → teen → adult → senior`` tier plus a visible scale/accessory
 *      choice. Pinning the boundaries here is how we keep the "cute morph"
 *      from drifting over time.
 *   2. The component itself renders in every scene without throwing so the
 *      survey can mount a page per modality safely.
 */

import React from "react";
import { render } from "@testing-library/react-native";

import MascotActor, { poseForAge, tierForAge, type MascotScene } from "../components/MascotActor";

// MascotActor runs persistent Animated.loop timers (idle bob / pointing pulse).
// Fake timers prevent those loops from leaking past the Jest teardown and
// spraying "accessed after environment torn down" warnings in the CI log.
jest.useFakeTimers();

// The i18n hook is a thin React context; the mascot only reads `locale`.
jest.mock("../i18n", () => ({
  useT: () => ({ locale: "en", t: (k: string) => k }),
}));

// Avoid pulling the full mascots asset map in during tests.
jest.mock("../mascot", () => ({
  mascotImageForLocale: () => 1,
}));

describe("poseForAge", () => {
  it("classifies the four age tiers at their boundaries", () => {
    expect(tierForAge(3)).toBe("child");
    expect(tierForAge(12)).toBe("child");
    expect(tierForAge(13)).toBe("teen");
    expect(tierForAge(19)).toBe("teen");
    expect(tierForAge(20)).toBe("adult");
    expect(tierForAge(59)).toBe("adult");
    expect(tierForAge(60)).toBe("senior");
    expect(tierForAge(120)).toBe("senior");
  });

  it("picks a visibly smaller scale for children than for adults", () => {
    expect(poseForAge(7).scale).toBeLessThan(poseForAge(40).scale);
    expect(poseForAge(7).scale).toBeLessThan(poseForAge(16).scale);
  });

  it("gives seniors a glasses accessory and children a child silhouette", () => {
    expect(poseForAge(72).accessory).toBe("👓");
    expect(poseForAge(8).accessory).toBe("🧒");
    expect(poseForAge(40).accessory).toBe("");
  });

  it("falls back to adult pose for non-finite ages", () => {
    expect(tierForAge(Number.NaN)).toBe("adult");
    expect(tierForAge(Number.POSITIVE_INFINITY)).toBe("adult");
  });
});

describe("MascotActor smoke renders", () => {
  const scenes: MascotScene[] = [
    { kind: "idle" },
    { kind: "flyin-point", pointAt: "right" },
    { kind: "flyin-point", pointAt: "left" },
    { kind: "flyin-point", pointAt: "down" },
    { kind: "dance" },
    { kind: "age-morph", age: 7 },
    { kind: "age-morph", age: 72 },
    { kind: "video" },
    { kind: "teacher" },
    { kind: "presentation" },
    { kind: "reading" },
    { kind: "tutoring" },
    { kind: "gaming" },
  ];

  it.each(scenes.map((s) => [s.kind, s]))(
    "mounts scene %s without throwing",
    (_label, scene) => {
      const { getByTestId, unmount } = render(<MascotActor scene={scene as MascotScene} />);
      expect(getByTestId("mascot-actor")).toBeTruthy();
      expect(getByTestId("mascot-actor-image")).toBeTruthy();
      unmount();
    },
  );
});

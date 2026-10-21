import React from "react";
import { fireEvent, render } from "@testing-library/react-native";

import FirstSignInAssistant from "../components/FirstSignInAssistant";

jest.mock("expo-av", () => ({ Audio: {} }));
jest.mock("expo-file-system", () => ({ deleteAsync: jest.fn(), readAsStringAsync: jest.fn(), EncodingType: {} }));
jest.mock("expo-image-picker", () => ({ CameraType: { front: "front", back: "back" } }));

jest.mock("../components/KenBurnsImage", () => {
  const React = require("react");
  const { View } = require("react-native");
  return { __esModule: true, default: () => React.createElement(View) };
});

// MascotActor spins Animated loops - stub it out for walker/age tests so
// Jest doesn't fire act() warnings over something unrelated to the behavior
// under test. Dedicated coverage lives in mascotActor.test.tsx.
jest.mock("../components/MobileMascotMeshy", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    __esModule: true,
    default: ({ scene }: { scene: { kind: string; age?: number } }) =>
      React.createElement(View, { testID: `mascot-stub-${scene.kind}${scene.age ? `-${scene.age}` : ""}` }),
  };
});

jest.mock("../api", () => ({
  completeMobileAccountOnboarding: jest.fn(),
  getMe: jest.fn(() => Promise.resolve(null)),
  getMobileFreePlanOffer: jest.fn(() => Promise.resolve({ available: true, reason: "" })),
  selectMobileFreePlan: jest.fn(),
  submitLearningProfile: jest.fn(() => Promise.resolve({})),
  submitMobileOnboardingLearner: jest.fn(() => Promise.resolve({ studentId: "stu-1" })),
  submitOnboardingSurveyAnalytics: jest.fn(() => Promise.resolve()),
  getMobileSetupState: jest.fn(() => new Promise(() => undefined)),
}));

const student = {
  id: "stu-1",
  display_name: "Maya",
  age_band: "adult",
  mastery: {},
  completed_course_ids: [],
  interests: [],
};

describe("FirstSignInAssistant", () => {
  test("asks for a profile name and an age from the wheel, not a legal name or steppers", () => {
    const screen = render(<FirstSignInAssistant visible student={student} onComplete={() => undefined} />);
    expect(screen.getByText("Profile name")).toBeTruthy();
    expect(screen.getByText(/doesn’t need to be your legal name/)).toBeTruthy();
    expect(screen.getByDisplayValue("Maya")).toBeTruthy();
    expect(screen.getByTestId("age-wheel")).toBeTruthy();
    expect(screen.queryByText("−")).toBeNull();
    expect(screen.queryByText("+")).toBeNull();
    expect(screen.queryByText(/first name/i)).toBeNull();
  });

  test("about step mounts the age-morph mascot once an age is picked", () => {
    // Before any age is selected the mascot sits in idle. Once the wheel
    // publishes an age the About step swaps to the age-morph scene, which is
    // what makes the mascot grow / shrink / put on glasses for the senior
    // tier - this is the big marketing animation the user asked for.
    const screen = render(<FirstSignInAssistant visible student={student} onComplete={() => undefined} />);
    expect(screen.getByTestId("mascot-stub-idle")).toBeTruthy();
    // AgeWheel is a scroll picker, but tapping an age label commits that age.
    fireEvent.press(screen.getByText("42"));
    expect(screen.getByTestId("mascot-stub-age-morph-42")).toBeTruthy();
    fireEvent.press(screen.getByText("8"));
    expect(screen.getByTestId("mascot-stub-age-morph-8")).toBeTruthy();
    fireEvent.press(screen.getByText("72"));
    expect(screen.getByTestId("mascot-stub-age-morph-72")).toBeTruthy();
  });

  test("learn step walks one modality per page with all ten rating choices", async () => {
    // The survey is now one-page-per-choice: the learner sees exactly one
    // modality card at a time, acts out by Sala in the art pane. This test
    // walks the full six pages, confirms each one shows ONLY its own 1-10
    // rating row (not the others), and that Next advances the walker.
    const screen = render(<FirstSignInAssistant visible student={student} onComplete={() => undefined} />);
    fireEvent.press(screen.getByText("40"));
    fireEvent.press(screen.getByText("Continue"));
    await screen.findByText("How do you learn best?");
    const modes = ["video", "live_teacher", "presentation", "reading", "tutoring", "gaming"] as const;
    for (let i = 0; i < modes.length; i += 1) {
      const mode = modes[i];
      // Current page is the Nth modality.
      expect(screen.getByTestId(`learn-page-${mode}`)).toBeTruthy();
      // Full 1-10 rating row for this modality is visible.
      for (let n = 1; n <= 10; n += 1) {
        expect(screen.getByTestId(`rate-${mode}-${n}`)).toBeTruthy();
      }
      // No other modality's rating row leaks onto this page.
      for (const other of modes) {
        if (other === mode) continue;
        expect(screen.queryByTestId(`rate-${other}-1`)).toBeNull();
      }
      // Rate 7 and advance (last page's button is "Finish", not "Next").
      fireEvent.press(screen.getByTestId(`rate-${mode}-7`));
      if (i < modes.length - 1) {
        fireEvent.press(screen.getByText("Next"));
      }
    }
  });
});

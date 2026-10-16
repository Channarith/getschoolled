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

  test("every learning mode shows all ten rating choices", async () => {
    const screen = render(<FirstSignInAssistant visible student={student} onComplete={() => undefined} />);
    fireEvent.press(screen.getByText("40"));
    fireEvent.press(screen.getByText("Continue"));
    await screen.findByText("How do you learn best?");
    for (const mode of ["video", "live_teacher", "presentation", "reading", "tutoring", "gaming"]) {
      for (let n = 1; n <= 10; n += 1) {
        expect(screen.getByTestId(`rate-${mode}-${n}`)).toBeTruthy();
      }
    }
  });
});

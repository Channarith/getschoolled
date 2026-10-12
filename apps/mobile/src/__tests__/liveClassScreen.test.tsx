import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import LiveClassScreen from "../screens/LiveClassScreen";

const mockListLessons = jest.fn();

jest.mock("../api", () => ({
  listLessons: (...args: unknown[]) => mockListLessons(...args),
}));

jest.mock("../hooks/useAndroidBack", () => ({
  useAndroidBackTo: () => undefined,
}));

jest.mock("../i18n", () => ({
  useT: () => ({
    t: (key: string) => key,
    locale: "en",
  }),
}));

jest.mock("../components/StudioCourseSection", () => {
  const { Text, View } = require("react-native");
  return function MockStudio() {
    return (
      <View testID="studio-section">
        <Text>studio</Text>
      </View>
    );
  };
});

// Spring/timing callbacks can keep the suite alive past CI's 5s default.
jest.mock("react-native/Libraries/Animated/NativeAnimatedHelper");

describe("LiveClassScreen", () => {
  beforeEach(() => {
    mockListLessons.mockReset();
    mockListLessons.mockResolvedValue([
      {
        lesson_id: "ai-fluency-essentials",
        title: "AI Fluency: Essentials for the Modern Workplace",
        level: "Foundation",
        audience: "general",
        track: "AI",
      },
      {
        lesson_id: "cpr-first-aid-certification",
        title: "CPR and First Aid Certification",
        audience: "general",
        track: "CPR",
      },
      {
        lesson_id: "   ",
        title: "",
      },
    ]);
  });

  // Render + async list load + sticky footer animation can exceed 5s in CI.
  it(
    "scrolls catalog content above the sticky Start bar and drops empty rows",
    async () => {
      const onStart = jest.fn();
      render(
        <LiveClassScreen
          onStart={onStart}
          onOpenLiveRooms={() => undefined}
          onBack={() => undefined}
        />,
      );

      expect(await screen.findByTestId("live-class-screen")).toBeTruthy();
      expect(await screen.findByTestId("live-class-lesson-ai-fluency-essentials")).toBeTruthy();
      expect(screen.getByTestId("live-class-lesson-cpr-first-aid-certification")).toBeTruthy();
      expect(screen.queryByTestId("live-class-lesson-   ")).toBeNull();
      expect(screen.getByText("CPR and First Aid Certification")).toBeTruthy();
      expect(screen.getByTestId("live-class-sticky-start")).toBeTruthy();

      fireEvent.press(screen.getByTestId("live-class-lesson-ai-fluency-essentials"));
      fireEvent.press(screen.getByText("▶  Start"));

      await waitFor(() => {
        expect(onStart).toHaveBeenCalledWith(
          "ai-fluency-essentials",
          "AI Fluency: Essentials for the Modern Workplace",
          "solo",
        );
      });
    },
    15000,
  );
});

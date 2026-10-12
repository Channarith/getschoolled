import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

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

  it("scrolls catalog content above the sticky Start bar and drops empty rows", async () => {
    const onStart = jest.fn();
    const { getByTestId, queryByTestId, getByText } = render(
      <LiveClassScreen
        onStart={onStart}
        onOpenLiveRooms={() => undefined}
        onBack={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(getByTestId("live-class-screen")).toBeTruthy();
      expect(getByTestId("live-class-lesson-ai-fluency-essentials")).toBeTruthy();
      expect(getByTestId("live-class-lesson-cpr-first-aid-certification")).toBeTruthy();
    });

    expect(queryByTestId("live-class-lesson-   ")).toBeNull();
    expect(getByText("CPR and First Aid Certification")).toBeTruthy();
    expect(getByTestId("live-class-sticky-start")).toBeTruthy();

    fireEvent.press(getByTestId("live-class-lesson-ai-fluency-essentials"));
    fireEvent.press(getByText("▶  Start"));

    expect(onStart).toHaveBeenCalledWith(
      "ai-fluency-essentials",
      "AI Fluency: Essentials for the Modern Workplace",
      "solo",
    );
  });
});

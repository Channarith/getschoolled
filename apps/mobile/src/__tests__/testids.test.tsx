/**
 * testID plumbing for Maestro (QA V&V plan, Mobile E2E).
 *
 * Maestro flows target stable testIDs, not localized text. This verifies the
 * forwarding actually reaches the rendered Pressable — AnimatedPressable spreads
 * props through, and PrimaryButton passes testID down — so the .maestro flows
 * have real anchors. Renders with @testing-library/react-native (no device).
 */

import React from "react";
import { render } from "@testing-library/react-native";

import BottomTabs from "../components/BottomTabs";
import PrimaryButton from "../components/PrimaryButton";

// BottomTabs pulls tab labels from the i18n hook; stub it to the key so no
// provider is needed.
jest.mock("../i18n", () => ({ useT: () => ({ t: (k: string) => k }) }));

describe("BottomTabs testIDs", () => {
  test("renders a stable testID for each of the six tabs", () => {
    const { getByTestId } = render(<BottomTabs active="home" onChange={() => {}} />);
    for (const id of ["home", "drive", "mylist", "careers", "notifications", "settings"]) {
      expect(getByTestId(`tab-${id}`)).toBeTruthy();
    }
  });
});

describe("PrimaryButton testID", () => {
  test("forwards testID to the underlying pressable", () => {
    const { getByTestId } = render(
      <PrimaryButton label="Go" testID="auth-submit" onPress={() => {}} />,
    );
    expect(getByTestId("auth-submit")).toBeTruthy();
  });

  test("ghost variant also forwards testID", () => {
    const { getByTestId } = render(
      <PrimaryButton label="Guest" variant="ghost" testID="auth-guest" onPress={() => {}} />,
    );
    expect(getByTestId("auth-guest")).toBeTruthy();
  });
});

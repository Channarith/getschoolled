import React from "react";
import { fireEvent, render } from "@testing-library/react-native";

import GuestHomeScreen from "../screens/GuestHomeScreen";

jest.mock("../i18n", () => ({
  useT: () => ({
    locale: "en",
    t: (key: string) =>
      ({
        "guest.kicker": "Guided practice",
        "guest.tryDemo": "Try the demo",
        "guest.logIn": "Log in",
        "guest.back": "← Back",
      })[key] ?? key,
  }),
}));

jest.mock("../screens/AuthScreen", () => {
  const React = require("react");
  const { View } = require("react-native");
  function AuthScreen() {
    return React.createElement(View, { testID: "auth-screen" });
  }
  return { __esModule: true, default: AuthScreen };
});

jest.mock("../screens/DemoWebScreen", () => {
  const React = require("react");
  const { View } = require("react-native");
  function DemoWebScreen() {
    return React.createElement(View, { testID: "demo-web" });
  }
  return { __esModule: true, default: DemoWebScreen };
});

describe("GuestHomeScreen", () => {
  test("opens the demo picker and the login page from the landing", () => {
    const screen = render(<GuestHomeScreen />);
    expect(screen.getByTestId("guest-landing")).toBeTruthy();

    fireEvent.press(screen.getByTestId("guest-try-demo"));
    expect(screen.getByTestId("guest-demo-drivers-ed")).toBeTruthy();
    expect(screen.queryByTestId("guest-demo-on-the-go")).toBeNull();
    expect(screen.getByTestId("guest-demo-arcade")).toBeTruthy();

    fireEvent.press(screen.getByTestId("guest-back"));
    fireEvent.press(screen.getByTestId("guest-log-in"));
    expect(screen.getByTestId("auth-screen")).toBeTruthy();
  });

  test("opens a demo from the picker", () => {
    const screen = render(<GuestHomeScreen />);
    fireEvent.press(screen.getByTestId("guest-try-demo"));
    fireEvent.press(screen.getByTestId("guest-demo-arcade"));
    expect(screen.getByTestId("demo-web")).toBeTruthy();
  });

  test("four quick taps on the logo open the hidden audio demo; fewer do not", () => {
    const screen = render(<GuestHomeScreen />);
    const brand = screen.getByText("Salareen");
    for (let i = 0; i < 3; i += 1) fireEvent.press(brand);
    expect(screen.queryByTestId("demo-web")).toBeNull();
    fireEvent.press(brand);
    expect(screen.getByTestId("demo-web")).toBeTruthy();
  });
});

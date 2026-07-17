/**
 * ErrorBoundary catches a crashing screen so one bad screen (e.g. the live room)
 * shows a readable, dismissible message + logs the stack, instead of white-screen
 * crashing the whole app. Renders with @testing-library/react-native (no device).
 */

import React from "react";
import { Text } from "react-native";
import { render, fireEvent } from "@testing-library/react-native";

import ErrorBoundary from "../components/ErrorBoundary";

function Boom(): React.ReactElement {
  throw new Error("kaboom in live room");
}

describe("ErrorBoundary", () => {
  // The boundary logs via console.error on catch; silence it for a clean run.
  let spy: jest.SpyInstance;
  beforeEach(() => { spy = jest.spyOn(console, "error").mockImplementation(() => {}); });
  afterEach(() => { spy.mockRestore(); });

  test("renders children normally when nothing throws", () => {
    const { getByText, queryByText } = render(
      <ErrorBoundary><Text>healthy screen</Text></ErrorBoundary>,
    );
    expect(getByText("healthy screen")).toBeTruthy();
    expect(queryByText("Something went wrong on this screen")).toBeNull();
  });

  test("shows the fallback (not a crash) and the error message when a child throws", () => {
    const { getByText } = render(
      <ErrorBoundary><Boom /></ErrorBoundary>,
    );
    expect(getByText("Something went wrong on this screen")).toBeTruthy();
    expect(getByText("kaboom in live room")).toBeTruthy();
    expect(spy).toHaveBeenCalled();  // logged for adb logcat / Metro
  });

  test("Go back invokes onReset so the app can return to a safe screen", () => {
    const onReset = jest.fn();
    const { getByText } = render(
      <ErrorBoundary onReset={onReset}><Boom /></ErrorBoundary>,
    );
    fireEvent.press(getByText("Go back"));
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  test("changing resetKey (navigating away) clears the error and recovers", () => {
    const { getByText, queryByText, rerender } = render(
      <ErrorBoundary resetKey="live-room"><Boom /></ErrorBoundary>,
    );
    expect(getByText("Something went wrong on this screen")).toBeTruthy();
    // Navigate elsewhere: new resetKey + a healthy child.
    rerender(
      <ErrorBoundary resetKey="home"><Text>home screen</Text></ErrorBoundary>,
    );
    expect(getByText("home screen")).toBeTruthy();
    expect(queryByText("Something went wrong on this screen")).toBeNull();
  });
});

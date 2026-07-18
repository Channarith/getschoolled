import { BackHandler, Platform } from "react-native";
import { renderHook, act } from "@testing-library/react-native";

import { useAndroidBack, useAndroidBackTo } from "../hooks/useAndroidBack";

describe("useAndroidBack", () => {
  const originalOS = Platform.OS;
  let handler: (() => boolean) | null = null;
  let remove: jest.Mock;

  beforeEach(() => {
    handler = null;
    remove = jest.fn();
    Object.defineProperty(Platform, "OS", { configurable: true, get: () => "android" });
    jest.spyOn(BackHandler, "addEventListener").mockImplementation(((_event, fn) => {
      handler = fn as () => boolean;
      return { remove };
    }) as typeof BackHandler.addEventListener);
  });

  afterEach(() => {
    Object.defineProperty(Platform, "OS", { configurable: true, get: () => originalOS });
    jest.restoreAllMocks();
  });

  it("consumes hardware back when handler returns true", () => {
    const onBack = jest.fn(() => true);
    renderHook(() => useAndroidBack(onBack));
    expect(handler?.()).toBe(true);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("allows default exit when handler returns false", () => {
    const onBack = jest.fn(() => false);
    renderHook(() => useAndroidBack(onBack));
    expect(handler?.()).toBe(false);
  });

  it("useAndroidBackTo always consumes and calls onBack", () => {
    const onBack = jest.fn();
    renderHook(() => useAndroidBackTo(onBack));
    expect(handler?.()).toBe(true);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("does not register when disabled", () => {
    const onBack = jest.fn(() => true);
    renderHook(() => useAndroidBack(onBack, false));
    expect(BackHandler.addEventListener).not.toHaveBeenCalled();
    expect(handler).toBeNull();
  });

  it("uses the latest handler after rerender", () => {
    const first = jest.fn(() => true);
    const second = jest.fn(() => true);
    const { rerender } = renderHook(
      ({ fn }) => useAndroidBack(fn),
      { initialProps: { fn: first } },
    );
    act(() => { rerender({ fn: second }); });
    expect(handler?.()).toBe(true);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("removes the listener on unmount", () => {
    const { unmount } = renderHook(() => useAndroidBack(() => true));
    unmount();
    expect(remove).toHaveBeenCalled();
  });
});

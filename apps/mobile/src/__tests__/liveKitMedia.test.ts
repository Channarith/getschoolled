import {
  isLiveKitMediaDowngraded,
  isLiveKitMediaUsable,
} from "../components/liveKitMedia";
import type { LiveKitMedia } from "../api";

describe("liveKitMedia", () => {
  test("isLiveKitMediaUsable requires url and token", () => {
    expect(isLiveKitMediaUsable(null)).toBe(false);
    expect(isLiveKitMediaUsable(undefined)).toBe(false);
    expect(
      isLiveKitMediaUsable({
        room: "r1",
        identity: "u1",
        token: "",
        url: "wss://lk.example",
      }),
    ).toBe(false);
    expect(
      isLiveKitMediaUsable({
        room: "r1",
        identity: "u1",
        token: "a.b.c",
        url: "",
      }),
    ).toBe(false);
    expect(
      isLiveKitMediaUsable({
        room: "r1",
        identity: "u1",
        token: "a.b.c",
        url: "wss://lk.example",
      }),
    ).toBe(true);
  });

  test("isLiveKitMediaDowngraded detects token without url", () => {
    const downgraded: LiveKitMedia = {
      room: "r1",
      identity: "u1",
      token: "a.b.c",
      url: "",
    };
    expect(isLiveKitMediaDowngraded(downgraded)).toBe(true);
    expect(isLiveKitMediaUsable(downgraded)).toBe(false);
    expect(
      isLiveKitMediaDowngraded({
        room: "r1",
        identity: "u1",
        token: "",
        url: "",
      }),
    ).toBe(false);
  });
});

/**
 * Guard against the "white text on white card" regression.
 *
 * The setup assistant renders AuthScreen with ``setup`` set, and setup mode
 * draws inputs on a near-white card. The dark-theme defaults
 * (``theme.colors.text = "#e8ecf6"``) produced effectively invisible
 * name/email/password text in that mode. This test pins two guarantees so a
 * future refactor cannot silently regress it:
 *
 *   1. The setup-mode input text color is darker than the background it sits
 *      on (so names / emails / passwords are readable).
 *   2. The setup-mode placeholder is darker than the dark-theme muted token
 *      (which was tuned for a dark backdrop and is unreadable on white).
 *
 * AuthScreen exports `SETUP_INPUT_TOKENS` purely so this test can introspect
 * the chosen colors without rendering the whole screen (which drags in Expo
 * Google/Apple providers and a live auth context).
 */

import { SETUP_INPUT_TOKENS } from "../screens/AuthScreen";

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const n = h.length === 3
    ? h.split("").map((c) => parseInt(c + c, 16))
    : [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  // Rec.709 luma - good enough for a contrast guard.
  return 0.2126 * n[0] + 0.7152 * n[1] + 0.0722 * n[2];
}

describe("AuthScreen setup-mode input contrast", () => {
  it("uses near-black input text on a near-white background", () => {
    // Text must be at least ~160 luma darker than the background so the
    // user can actually read what they typed.
    const bg = luminance(SETUP_INPUT_TOKENS.background);
    const text = luminance(SETUP_INPUT_TOKENS.text);
    expect(bg).toBeGreaterThan(230);
    expect(text).toBeLessThan(60);
    expect(bg - text).toBeGreaterThan(170);
  });

  it("uses a placeholder darker than the dark-theme muted token", () => {
    // Dark-theme muted (`#9aa6c2`) has luma ~162. Setup placeholder must sit
    // comfortably below that so it reads on a white card.
    expect(luminance(SETUP_INPUT_TOKENS.placeholder)).toBeLessThan(140);
  });

  it("has a visible border separate from the background", () => {
    // Border and background cannot share the same luminance - otherwise the
    // input looks like a floating line of text with no field edges.
    expect(luminance(SETUP_INPUT_TOKENS.border))
      .not.toBe(luminance(SETUP_INPUT_TOKENS.background));
  });
});

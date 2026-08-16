import {
  DEFAULT_LIGHTING_THRESHOLDS,
  NIGHT_VISION_THRESHOLDS,
  analyzeLuminanceGrid,
  isLightingReady,
  verdictFromMetrics,
} from "../cameraLighting";

function flatGrid(value: number, h = 36, w = 64): number[][] {
  return Array.from({ length: h }, () => Array(w).fill(value));
}

function sharpMidLitGrid(): number[][] {
  // Vertical bars (period 4) — Sobel Gx sees real edges; mid exposure.
  return Array.from({ length: 36 }, () =>
    Array.from({ length: 64 }, (_, x) => (Math.floor(x / 4) % 2 === 0 ? 0.28 : 0.72)),
  );
}

describe("cameraLighting readiness", () => {
  it("passes a mid-lit sharp grid when a face is held", () => {
    const metrics = analyzeLuminanceGrid(sharpMidLitGrid());
    expect(metrics.blurry).toBe(false);
    expect(metrics.underexposed).toBe(false);
    expect(metrics.overexposed).toBe(false);
    const result = verdictFromMetrics(metrics, { facePresent: true });
    expect(result.verdict).toBe("ready");
    expect(isLightingReady(result.verdict)).toBe(true);
  });

  it("blocks a near-black room without night vision", () => {
    const metrics = analyzeLuminanceGrid(flatGrid(0.04));
    const result = verdictFromMetrics(metrics, { facePresent: true });
    expect(["blocked_dark", "fixable"]).toContain(result.verdict);
    expect(isLightingReady(result.verdict)).toBe(false);
  });

  it("allows a dark room when night vision is on and a face is held", () => {
    // Dim vertical bars: underexposed for default, usable under night gates.
    const grid = Array.from({ length: 36 }, () =>
      Array.from({ length: 64 }, (_, x) => (Math.floor(x / 4) % 2 === 0 ? 0.05 : 0.14)),
    );
    const metrics = analyzeLuminanceGrid(grid, NIGHT_VISION_THRESHOLDS);
    const result = verdictFromMetrics(metrics, {
      facePresent: true,
      nightVision: true,
      thresholds: NIGHT_VISION_THRESHOLDS,
    });
    expect(result.verdict).toBe("ready");
    expect(result.nightVision).toBe(true);
  });

  it("blocks when no face is present even if lighting looks fine", () => {
    const metrics = analyzeLuminanceGrid(
      sharpMidLitGrid(),
      DEFAULT_LIGHTING_THRESHOLDS,
    );
    const result = verdictFromMetrics(metrics, { facePresent: false });
    expect(result.verdict).toBe("blocked_no_face");
  });

  it("flags blown-out frames", () => {
    const metrics = analyzeLuminanceGrid(flatGrid(0.97));
    expect(metrics.overexposed).toBe(true);
    const result = verdictFromMetrics(metrics, { facePresent: true });
    expect(["blocked_bright", "fixable"]).toContain(result.verdict);
  });
});

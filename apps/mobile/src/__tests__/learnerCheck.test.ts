import { ageAtOffset, AGE_ROW_HEIGHT } from "../components/AgeWheel";
import { stillMatchesTarget } from "../components/BiometricSetupModal";
import {
  AGE_OPTIONS,
  POSES,
  faceContour,
  faceGeometry,
  meteringToLevel,
  poseFromBaseline,
  shuffledPoses,
  svgPath,
  waveformBars,
} from "../learnerCheck";

jest.mock("expo-av", () => ({ Audio: {} }));
jest.mock("expo-file-system", () => ({ deleteAsync: jest.fn(), readAsStringAsync: jest.fn(), EncodingType: {} }));
jest.mock("expo-image-picker", () => ({ CameraType: { front: "front", back: "back" } }));

const FRONTAL = [[247, 121], [312, 121], [279, 151], [248, 179], [308, 180]];

describe("Learner Check helpers (native)", () => {
  it("age wheel covers 3-120 and snaps offsets to whole ages", () => {
    expect(AGE_OPTIONS[0]).toBe(3);
    expect(AGE_OPTIONS[AGE_OPTIONS.length - 1]).toBe(120);
    expect(ageAtOffset(0)).toBe(3);
    expect(ageAtOffset(AGE_ROW_HEIGHT * 9 + 10)).toBe(12);
    expect(ageAtOffset(-200)).toBe(3);
    expect(ageAtOffset(AGE_ROW_HEIGHT * 500)).toBe(120);
  });

  it("look targets are a shuffled set of all four directions", () => {
    const orders = new Set<string>();
    for (let i = 0; i < 30; i += 1) {
      const order = shuffledPoses();
      expect([...order].sort()).toEqual([...POSES].sort());
      orders.add(order.join());
    }
    expect(orders.size).toBeGreaterThan(3);
  });

  it("draws a contour around the landmarks and hides it without them", () => {
    const contour = faceContour(FRONTAL);
    expect(contour).not.toBeNull();
    const ys = contour!.outline.map(([, y]) => y);
    expect(Math.min(...ys)).toBeLessThan(121);
    expect(Math.max(...ys)).toBeGreaterThan(180);
    expect(svgPath(contour!.outline, true)).toMatch(/^M.* Z$/);
    expect(faceContour(undefined)).toBeNull();
    expect(faceContour([[1, 2]])).toBeNull();
  });

  it("maps expo-av metering onto waveform bars that fill left to right", () => {
    expect(meteringToLevel(-160)).toBe(0);
    expect(meteringToLevel(undefined)).toBe(0);
    expect(meteringToLevel(0)).toBe(1);
    expect(meteringToLevel(-30)).toBeGreaterThan(meteringToLevel(-45));
    const samples = [0, 1, 2, 3].map((t) => ({ t, level: meteringToLevel(-20) }));
    const bars = waveformBars(samples, 10, 10);
    expect(bars.slice(0, 4).every((h) => h > 0.6)).toBe(true);
    expect(bars.slice(4).every((h) => h === 0)).toBe(true);
  });

  it("registers a clear mirrored look that the old mouth-axis yaw missed", () => {
    const project = (yawDeg: number, pitchDeg: number) => {
      const iod = 63;
      const pts = [
        [-iod / 2, 0, 0],
        [iod / 2, 0, 0],
        [0, 32, 30],
        [-25, 68, 18],
        [25, 68, 18],
      ];
      const yaw = (yawDeg * Math.PI) / 180;
      const pitch = (pitchDeg * Math.PI) / 180;
      const cy = Math.cos(yaw);
      const sy = Math.sin(yaw);
      const cp = Math.cos(pitch);
      const sp = Math.sin(pitch);
      return pts.map(([x, y, z]) => {
        const x1 = x * cy + z * sy;
        const z1 = -x * sy + z * cy;
        const y2 = y * cp + z1 * sp;
        return [320 + x1 * 3.2, 180 + y2 * 3.2];
      });
    };
    const box = [220, 80, 200, 260];
    const frame = [640, 480];
    const neutralLm = project(0, 0);
    const neutral = faceGeometry(neutralLm, box, frame);
    expect(neutral).not.toBeNull();
    const turned = project(20, 0);
    const axisYaw = (landmarks: number[][]) => {
      const [rightEye, leftEye, nose, rightMouth, leftMouth] = landmarks;
      const eyeDist = Math.hypot(leftEye[0] - rightEye[0], leftEye[1] - rightEye[1]);
      const axisX = (rightEye[0] + leftEye[0] + rightMouth[0] + leftMouth[0]) / 4;
      return (nose[0] - axisX) / eyeDist;
    };
    expect(Math.abs(axisYaw(turned) - axisYaw(neutralLm))).toBeLessThan(0.16);
    expect(poseFromBaseline(neutral!, faceGeometry(turned, box, frame)!)).toBe("left");
    expect(poseFromBaseline(neutral!, faceGeometry(project(-20, 0), box, frame)!)).toBe("right");
    expect(poseFromBaseline(neutral!, faceGeometry(project(0, -12), box, frame)!)).toBe("up");
    expect(poseFromBaseline(neutral!, faceGeometry(project(0, 12), box, frame)!)).toBe("down");
    expect(poseFromBaseline(neutral!, faceGeometry(project(5, 4), box, frame)!)).toBeNull();
    expect(poseFromBaseline(neutral!, faceGeometry(turned, box, frame)!, false)).toBe("right");
  });

  it("accepts a sideways still either way the camera mirrored it, but not twice the same way", () => {
    expect(stillMatchesTarget("up", "up", null)).toBe(true);
    expect(stillMatchesTarget("up", "down", null)).toBe(false);
    expect(stillMatchesTarget("left", "right", null)).toBe(true);
    expect(stillMatchesTarget("right", "right", "right")).toBe(false);
    expect(stillMatchesTarget("left", null, null)).toBe(false);
  });
});

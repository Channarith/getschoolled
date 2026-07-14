/**
 * U-DRV-1 — driving-detection state machine (QA V&V plan, Mobile dimension).
 *
 * This singleton auto-launches Drive Mode and fires notifications, so its GPS
 * thresholds and timers are safety-relevant: a false positive launches the
 * hands-free UI at a bus stop; a false negative kills the feature; a leaked
 * timer keeps firing after teardown. We drive it through the (mocked)
 * expo-location watch callback with fake timers and assert every transition.
 *
 * Thresholds under test (from drivingDetection.ts):
 *   DRIVING >= 4.0 m/s sustained 12s ; IDLE < 1.5 m/s sustained 30s ;
 *   markNotDriving() suppresses re-entry for 10 min.
 */

// `mock`-prefixed so jest allows referencing them inside the hoisted factory.
const mockState: { speedCb?: (loc: { coords: { speed: number | null } }) => void } = {};
const mockLocation = {
  Accuracy: { Balanced: 3 },
  // Status-check-first flow (see locationPermission.ts): granted here so the
  // helper resolves without prompting.
  getForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted", canAskAgain: true }),
  requestForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
  watchPositionAsync: jest.fn(async (_opts: unknown, cb: (loc: { coords: { speed: number | null } }) => void) => {
    mockState.speedCb = cb;
    return { remove: jest.fn() };
  }),
};

jest.mock("../nativeModules", () => ({
  isExpoLocationAvailable: () => true,
  isExpoSensorsAvailable: () => false,
  tryRequireModule: (name: string) => (name === "expo-location" ? mockLocation : null),
}));

const SETTINGS = {
  driveDetectionEnabled: true,
  driveUseLocation: true,
  driveUseMotionSensors: false,
} as unknown as import("../storage").Settings;

let dd: typeof import("../drivingDetection");

async function startAndDriveTo(phase: "driving"): Promise<void> {
  await dd.startDrivingDetection(SETTINGS);
  mockState.speedCb!({ coords: { speed: 5 } }); // >= 4 m/s arms the enter timer
  jest.advanceTimersByTime(12_000); // sustained 12s -> driving
  expect(dd.getDrivingStatus().phase).toBe(phase);
}

beforeEach(() => {
  jest.resetModules();
  jest.useFakeTimers();
  mockState.speedCb = undefined;
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  dd = require("../drivingDetection");
});

afterEach(async () => {
  await dd.stopDrivingDetection();
  jest.clearAllTimers();
  jest.useRealTimers();
});

test("idle -> driving requires >= 4 m/s sustained for 12s", async () => {
  await dd.startDrivingDetection(SETTINGS);
  mockState.speedCb!({ coords: { speed: 5 } });
  expect(dd.getDrivingStatus().phase).not.toBe("driving");
  jest.advanceTimersByTime(11_999);
  expect(dd.getDrivingStatus().phase).not.toBe("driving");
  jest.advanceTimersByTime(1);
  expect(dd.getDrivingStatus().phase).toBe("driving");
});

test("a slow sample before 12s cancels the transition (no false positive)", async () => {
  await dd.startDrivingDetection(SETTINGS);
  mockState.speedCb!({ coords: { speed: 5 } });
  jest.advanceTimersByTime(11_900);
  mockState.speedCb!({ coords: { speed: 1 } }); // dropped below driving threshold
  jest.advanceTimersByTime(1_000);
  expect(dd.getDrivingStatus().phase).toBe("idle");
});

test("driving -> idle requires < 1.5 m/s sustained for 30s", async () => {
  await startAndDriveTo("driving");
  mockState.speedCb!({ coords: { speed: 0.5 } }); // arms the 30s exit timer
  jest.advanceTimersByTime(29_000);
  expect(dd.getDrivingStatus().phase).toBe("driving");
  jest.advanceTimersByTime(2_000);
  expect(dd.getDrivingStatus().phase).toBe("idle");
});

test("a fast sample mid-exit cancels the exit timer", async () => {
  await startAndDriveTo("driving");
  mockState.speedCb!({ coords: { speed: 0.5 } });
  jest.advanceTimersByTime(15_000);
  mockState.speedCb!({ coords: { speed: 5 } }); // back above idle threshold
  jest.advanceTimersByTime(30_000);
  expect(dd.getDrivingStatus().phase).toBe("driving");
});

test("markNotDriving forces idle and suppresses re-entry for 10 minutes", async () => {
  await startAndDriveTo("driving");
  dd.markNotDriving();
  expect(dd.getDrivingStatus().phase).toBe("idle");

  // Within the 10-min window, sustained driving speed must NOT re-launch.
  mockState.speedCb!({ coords: { speed: 6 } });
  jest.advanceTimersByTime(20_000);
  expect(dd.getDrivingStatus().phase).toBe("idle");

  // Past the window, detection resumes normally.
  jest.advanceTimersByTime(10 * 60_000);
  mockState.speedCb!({ coords: { speed: 6 } });
  jest.advanceTimersByTime(12_000);
  expect(dd.getDrivingStatus().phase).toBe("driving");
});

test("stopDrivingDetection clears timers (no leaked transition after teardown)", async () => {
  await dd.startDrivingDetection(SETTINGS);
  mockState.speedCb!({ coords: { speed: 5 } }); // arm enter timer
  await dd.stopDrivingDetection();
  jest.advanceTimersByTime(60_000);
  // Enter timer must have been cleared — no transition to driving post-teardown.
  expect(dd.getDrivingStatus().phase).not.toBe("driving");
});

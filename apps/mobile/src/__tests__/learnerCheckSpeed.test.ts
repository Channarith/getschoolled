import { DETECT_TIMEOUT_MS, detectDeviceFaces } from "../deviceFace";
import { SILENT_PEAK_DB, isSilentTake, withTimeout } from "../learnerCheck";
import { isDeferredUpload } from "../pendingUpload";

const mockDetect = jest.fn();
jest.mock("@react-native-ml-kit/face-detection", () => ({
  __esModule: true,
  default: { detect: (...args: unknown[]) => mockDetect(...args) },
}), { virtual: true });

describe("Learner Check timeouts", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => {
    jest.useRealTimers();
    mockDetect.mockReset();
  });

  it("withTimeout passes a fast result through", async () => {
    await expect(withTimeout(Promise.resolve(7), 1000, "slow")).resolves.toBe(7);
  });

  it("withTimeout rejects a promise that never settles", async () => {
    const pending = withTimeout(new Promise<never>(() => undefined), 1000, "Saving is taking too long.");
    const caught = pending.catch((reason: Error) => reason);
    jest.advanceTimersByTime(1000);
    expect((await caught).message).toBe("Saving is taking too long.");
  });

  it("withTimeout keeps the original rejection", async () => {
    await expect(withTimeout(Promise.reject(new Error("boom")), 1000, "slow")).rejects.toThrow("boom");
  });

  it("a stuck on-device read gives up instead of hanging the scan", async () => {
    mockDetect.mockReturnValue(new Promise(() => undefined));
    const caught = detectDeviceFaces("file:///frame.jpg").catch((reason: Error) => reason);
    jest.advanceTimersByTime(DETECT_TIMEOUT_MS);
    expect(((await caught) as Error).message).toMatch(/took too long/);
  });

  it("a timed-out save is deferred to the phone, not shown as a refusal", () => {
    expect(isDeferredUpload(new Error("Saving the face check is taking too long."))).toBe(true);
    expect(isDeferredUpload(new Error("Saving the voice check is taking too long."))).toBe(true);
  });
});

describe("silent take check", () => {
  it("flags a take whose metering never rose to speech", () => {
    expect(isSilentTake(-80, true)).toBe(true);
    expect(isSilentTake(null, true)).toBe(true);
  });

  it("passes speech and phones that report no metering", () => {
    expect(isSilentTake(-20, true)).toBe(false);
    expect(isSilentTake(SILENT_PEAK_DB, true)).toBe(false);
    expect(isSilentTake(null, false)).toBe(false);
  });
});

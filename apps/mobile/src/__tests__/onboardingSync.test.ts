import AsyncStorage from "@react-native-async-storage/async-storage";

const mockSelectPlan = jest.fn();
const mockComplete = jest.fn();
const mockSaveProfile = jest.fn();

jest.mock("../api", () => ({
  selectMobileOnboardingPlan: (...args: unknown[]) => mockSelectPlan(...args),
  completeMobileAccountOnboarding: (...args: unknown[]) => mockComplete(...args),
  submitLearningProfile: (...args: unknown[]) => mockSaveProfile(...args),
}));
jest.mock("../storage", () => ({ getToken: () => "token-for-the-onboarding-outbox-test" }));

import {
  flushPendingOnboardingSync,
  hasPendingOnboardingSync,
  isRetryableIdentityWrite,
  queueLearningProfileSync,
  queueOnboardingSync,
} from "../onboardingSync";

describe("mobile onboarding outbox", () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
    mockSelectPlan.mockReset();
    mockComplete.mockReset();
    mockSaveProfile.mockReset();
  });

  it("treats a gateway timeout as retryable and a refusal as final", () => {
    expect(isRetryableIdentityWrite(Object.assign(new Error("upstream"), { status: 504 }))).toBe(true);
    expect(isRetryableIdentityWrite(new Error("onboarding completion failed: 503"))).toBe(true);
    expect(isRetryableIdentityWrite(new Error("Cannot reach backend at x. (Aborted)"))).toBe(true);
    expect(isRetryableIdentityWrite(Object.assign(new Error("Free plan is gone"), { status: 409 }))).toBe(false);
  });

  it("keeps the finish through an outage and sends it once identity answers", async () => {
    await queueLearningProfileSync("stu-1", { modality_ratings: { video: 8 } });
    expect(await hasPendingOnboardingSync()).toBe(false);
    await queueOnboardingSync("Ada", "adult", "free");
    expect(await hasPendingOnboardingSync()).toBe(true);

    mockSaveProfile.mockRejectedValueOnce(new Error("504 Gateway Time-out"));
    expect(await flushPendingOnboardingSync(true)).toBe(false);
    expect(await hasPendingOnboardingSync()).toBe(true);
    expect(mockSelectPlan).not.toHaveBeenCalled();

    expect(await flushPendingOnboardingSync()).toBe(false);
    expect(mockSaveProfile).toHaveBeenCalledTimes(1);

    expect(await flushPendingOnboardingSync(true)).toBe(true);
    expect(mockSaveProfile).toHaveBeenLastCalledWith("stu-1", { modality_ratings: { video: 8 } });
    expect(mockSelectPlan).toHaveBeenCalledWith("free");
    expect(mockComplete).toHaveBeenCalledWith("Ada", "adult");
    expect(await hasPendingOnboardingSync()).toBe(false);
  });

  it("drops a job identity refuses instead of retrying it", async () => {
    await queueOnboardingSync("Ada", "adult", "free");
    mockSelectPlan.mockRejectedValueOnce(Object.assign(new Error("not allowed"), { status: 403 }));
    expect(await flushPendingOnboardingSync(true)).toBe(false);
    expect(await hasPendingOnboardingSync()).toBe(false);
  });
});

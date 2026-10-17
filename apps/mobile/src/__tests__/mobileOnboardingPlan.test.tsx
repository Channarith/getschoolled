import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import MobileOnboardingPlanStep from "../components/MobileOnboardingPlanStep";

jest.mock("../components/KenBurnsImage", () => {
  const React = require("react");
  const { View } = require("react-native");
  return { __esModule: true, default: () => React.createElement(View) };
});

const plans = {
  free: { tier: "free", display_name: "Free", price_usd: 0, billing_interval: "monthly", ads: true, blurb: "trial" },
  basic: { tier: "basic", display_name: "Standard", price_usd: 19, billing_interval: "monthly", ads: true, blurb: "5 languages" },
  pro: { tier: "pro", display_name: "Pro", price_usd: 29, billing_interval: "monthly", ads: false, blurb: "ad-free" },
  premium: { tier: "premium", display_name: "VIP", price_usd: 39, billing_interval: "monthly", ads: false, blurb: "all" },
};

jest.mock("../api", () => ({
  getConsumerPlans: jest.fn(() => Promise.resolve(plans)),
  getMobileFreePlanOffer: jest.fn(() => Promise.resolve({ available: false, reason: "Redis unavailable" })),
  getMe: jest.fn(() => Promise.resolve({ id: "acct-1" })),
  startMobileBillingCheckout: jest.fn(() => Promise.resolve({ session_id: "s1", url: "", provider: "sandbox" })),
  selectMobileOnboardingPlan: jest.fn(() => Promise.resolve()),
  completeMobileAccountOnboarding: jest.fn(() => Promise.resolve()),
}));

describe("MobileOnboardingPlanStep", () => {
  test("hides Free when the offer is unavailable and completes a paid plan", async () => {
    const onComplete = jest.fn();
    const api = require("../api");
    const screen = render(
      <MobileOnboardingPlanStep visible displayName="Maya" ageBand="adult" onComplete={onComplete} />,
    );
    await waitFor(() => expect(screen.queryByText("Free")).toBeNull());
    expect(screen.getByText("Standard")).toBeTruthy();
    fireEvent.press(screen.getByText("Continue to payment"));
    await waitFor(() => expect(api.selectMobileOnboardingPlan).toHaveBeenCalledWith("basic"));
    expect(onComplete).toHaveBeenCalled();
  });

  test("surfaces checkout/plan errors instead of dead-ending", async () => {
    const api = require("../api");
    api.selectMobileOnboardingPlan.mockRejectedValueOnce(new Error("402 paid tiers require verified payment"));
    const screen = render(
      <MobileOnboardingPlanStep visible displayName="Maya" ageBand="adult" onComplete={() => undefined} />,
    );
    await waitFor(() => screen.getByText("Standard"));
    fireEvent.press(screen.getByText("Continue to payment"));
    await waitFor(() => expect(screen.getByText(/402 paid tiers require verified payment/)).toBeTruthy());
  });
});

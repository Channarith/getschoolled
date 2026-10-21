import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import MobileOnboardingPlanStep from "../components/MobileOnboardingPlanStep";

jest.mock("../components/MobileMascotMeshy", () => {
  const React = require("react");
  const { View } = require("react-native");
  return { __esModule: true, default: () => React.createElement(View, { testID: "mobile-mascot-meshy" }) };
});

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
  submitMobileOnboardingBilling: jest.fn(() => Promise.resolve({ validated: true, card_last4: "4242" })),
  completeMobileAccountOnboarding: jest.fn(() => Promise.resolve()),
}));

function fillBilling(screen: ReturnType<typeof render>) {
  fireEvent.changeText(screen.getByLabelText("Street address"), "1348 Mokelumne Dr");
  fireEvent.changeText(screen.getByLabelText("City"), "Antioch");
  fireEvent.changeText(screen.getByLabelText("State"), "CA");
  fireEvent.changeText(screen.getByLabelText("ZIP"), "94531");
  fireEvent.changeText(screen.getByLabelText("Card number"), "4242 4242 4242 4242");
  fireEvent.changeText(screen.getByLabelText("MM"), "12");
  fireEvent.changeText(screen.getByLabelText("YYYY"), "2030");
  fireEvent.changeText(screen.getByLabelText("CVV"), "123");
}

describe("MobileOnboardingPlanStep", () => {
  beforeEach(() => jest.clearAllMocks());

  test("free plan claims and completes onboarding", async () => {
    const api = require("../api");
    api.getMobileFreePlanOffer.mockResolvedValueOnce({ available: true, reason: "" });
    const onComplete = jest.fn();
    const screen = render(
      <MobileOnboardingPlanStep visible displayName="Maya" ageBand="adult" onComplete={onComplete} />,
    );
    await waitFor(() => screen.getByText("Free"));
    fireEvent.press(screen.getByText("Start learning"));
    await waitFor(() => expect(api.selectMobileOnboardingPlan).toHaveBeenCalledWith("free"));
    expect(api.submitMobileOnboardingBilling).not.toHaveBeenCalled();
    await waitFor(() => expect(onComplete).toHaveBeenCalled());
  });

  test("sandbox paid plan saves billing before selecting the plan", async () => {
    const onComplete = jest.fn();
    const api = require("../api");
    const screen = render(
      <MobileOnboardingPlanStep visible displayName="Maya" ageBand="adult" onComplete={onComplete} />,
    );
    await waitFor(() => expect(screen.queryByText("Free")).toBeNull());
    fireEvent.press(screen.getByText("Continue to payment"));
    await waitFor(() => screen.getByText("Billing details."));
    expect(api.selectMobileOnboardingPlan).not.toHaveBeenCalled();
    fillBilling(screen);
    fireEvent.press(screen.getByText("Validate and start learning"));
    await waitFor(() => expect(api.selectMobileOnboardingPlan).toHaveBeenCalledWith("basic"));
    expect(api.submitMobileOnboardingBilling).toHaveBeenCalledWith(expect.objectContaining({
      card_number: "4242424242424242", exp_month: 12, exp_year: 2030, state: "CA", postal_code: "94531",
    }));
    const billingOrder = api.submitMobileOnboardingBilling.mock.invocationCallOrder[0];
    const planOrder = api.selectMobileOnboardingPlan.mock.invocationCallOrder[0];
    expect(billingOrder).toBeLessThan(planOrder);
    expect(onComplete).toHaveBeenCalled();
  });

  test("surfaces billing errors instead of dead-ending", async () => {
    const api = require("../api");
    api.submitMobileOnboardingBilling.mockRejectedValueOnce(new Error("card number failed validation"));
    const screen = render(
      <MobileOnboardingPlanStep visible displayName="Maya" ageBand="adult" onComplete={() => undefined} />,
    );
    await waitFor(() => screen.getByText("Standard"));
    fireEvent.press(screen.getByText("Continue to payment"));
    await waitFor(() => screen.getByText("Billing details."));
    fillBilling(screen);
    fireEvent.press(screen.getByText("Validate and start learning"));
    await waitFor(() => expect(screen.getByText(/card number failed validation/)).toBeTruthy());
    expect(api.selectMobileOnboardingPlan).not.toHaveBeenCalled();
  });
});

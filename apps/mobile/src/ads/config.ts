/** Mobile display ads (Google AdMob). Tier-gated like web AdSlot. */

import { Platform } from "react-native";
import Constants from "expo-constants";

const extra = (Constants.expoConfig?.extra || {}) as Record<string, string>;

/** Tiers with ad-free entitlement (matches aoep_shared.ads.AD_FREE_TIERS). */
export const AD_FREE_TIERS = new Set(["pro", "premium"]);

export function tierShowsAds(tier: string | undefined): boolean {
  return !AD_FREE_TIERS.has((tier || "free").toLowerCase());
}

/** Google sample / test banner unit IDs (safe for dev builds). */
export const TEST_BANNER_UNIT_ID = Platform.select({
  ios: "ca-app-pub-3940256099942544/2934735716",
  android: "ca-app-pub-3940256099942544/6300978111",
  default: "ca-app-pub-3940256099942544/6300978111",
}) as string;

/** Google sample / test interstitial unit IDs (safe for dev builds). */
export const TEST_INTERSTITIAL_UNIT_ID = Platform.select({
  ios: "ca-app-pub-3940256099942544/4411468910",
  android: "ca-app-pub-3940256099942544/1033173712",
  default: "ca-app-pub-3940256099942544/1033173712",
}) as string;

export function bannerUnitId(): string {
  const key = Platform.OS === "ios" ? "admobBannerIos" : "admobBannerAndroid";
  const configured = extra[key];
  if (configured && configured.includes("/")) {
    return configured;
  }
  return TEST_BANNER_UNIT_ID;
}

export function interstitialUnitId(): string {
  const key = Platform.OS === "ios" ? "admobInterstitialIos" : "admobInterstitialAndroid";
  const configured = extra[key];
  if (configured && configured.includes("/")) {
    return configured;
  }
  return TEST_INTERSTITIAL_UNIT_ID;
}

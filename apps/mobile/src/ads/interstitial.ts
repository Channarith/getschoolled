/** Interstitial ads (iOS + Android) for ad-supported tiers.
 *
 * Full-screen ad shown at natural breakpoints (e.g. before starting a lesson).
 * Native module only — no-op in Expo Go / when tier is ad-free. Fires an
 * impression beacon when the ad opens so it feeds the revenue ledger.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";

import type { InterstitialAd } from "react-native-google-mobile-ads";

import { interstitialUnitId, tierShowsAds } from "./config";
import { recordAdImpression } from "./revenue";
import { useFeatureFlag } from "../featureFlags";

type AdsModule = typeof import("react-native-google-mobile-ads");

let adsModule: AdsModule | null = null;
try {
  adsModule = require("react-native-google-mobile-ads") as AdsModule;
} catch {
  adsModule = null;
}

/**
 * Returns `{ ready, show }`. Call `show()` at a breakpoint; it returns true if
 * an ad was presented (so the caller can wait for CLOSED) or false to proceed
 * immediately (ad-free tier, not loaded, or native module unavailable).
 */
export function useInterstitial(tier?: string) {
  const adRef = useRef<InterstitialAd | null>(null);
  const [ready, setReady] = useState(false);
  const adsEnabled = useFeatureFlag("monetization.video_ads", false);

  useEffect(() => {
    if (!adsEnabled || !adsModule || !tierShowsAds(tier)) {
      setReady(false);
      adRef.current = null;
      return;
    }
    const { InterstitialAd: Interstitial, AdEventType } = adsModule;
    const ad = Interstitial.createForAdRequest(interstitialUnitId(), {
      requestNonPersonalizedAdsOnly: Platform.OS === "ios",
    });
    adRef.current = ad;

    const offLoaded = ad.addAdEventListener(AdEventType.LOADED, () => setReady(true));
    const offOpened = ad.addAdEventListener(AdEventType.OPENED, () => {
      recordAdImpression({
        placement: "mobile-interstitial", network: "admob", fmt: "video",
        tier, unit_id: interstitialUnitId(),
      });
    });
    const offClosed = ad.addAdEventListener(AdEventType.CLOSED, () => {
      setReady(false);
      ad.load();   // preload the next one
    });
    const offError = ad.addAdEventListener(AdEventType.ERROR, () => setReady(false));

    ad.load();
    return () => { offLoaded(); offOpened(); offClosed(); offError(); adRef.current = null; };
  }, [adsEnabled, tier]);

  const show = useCallback((): boolean => {
    if (adsEnabled && adsModule && ready && adRef.current) {
      try {
        adRef.current.show();
        return true;
      } catch {
        return false;
      }
    }
    return false;
  }, [adsEnabled, ready]);

  return { ready, show };
}

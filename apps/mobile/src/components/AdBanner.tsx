import { useEffect, useState } from "react";
import { Platform, StyleSheet, View } from "react-native";

import { bannerUnitId, tierShowsAds } from "../ads/config";
import { recordAdClick, recordAdImpression } from "../ads/revenue";
import { useFeatureFlag } from "../featureFlags";

type BannerModule = typeof import("react-native-google-mobile-ads");

let adsModule: BannerModule | null = null;
if (Platform.OS !== "web") {
  try {
    // Native module — requires dev client / EAS build (not Expo Go).
    // Metro also stubs this package on web via metro.config.js.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    adsModule = require("react-native-google-mobile-ads") as BannerModule;
  } catch {
    adsModule = null;
  }
}

type Props = {
  tier?: string;
  placement?: string;
};

/** Banner for free/basic members. Uses Google test units in dev; fires
 * impression/click beacons into the revenue ledger. */
export default function AdBanner({ tier, placement = "mobile-banner" }: Props) {
  const [ready, setReady] = useState(false);
  const adsEnabled = useFeatureFlag("monetization.video_ads", false);

  useEffect(() => {
    if (!adsEnabled || !adsModule || !tierShowsAds(tier)) {
      setReady(false);
      return;
    }
    let cancelled = false;
    void adsModule.default()
      .initialize()
      .then(() => { if (!cancelled) setReady(true); })
      .catch(() => { /* simulator without Play Services */ });
    return () => { cancelled = true; };
  }, [adsEnabled, tier]);

  if (!adsEnabled || !adsModule || !tierShowsAds(tier) || !ready) {
    return null;
  }

  const { BannerAd, BannerAdSize } = adsModule;
  return (
    <View style={styles.wrap} accessibilityLabel="Advertisement">
      <BannerAd
        unitId={bannerUnitId()}
        size={BannerAdSize.ANCHORED_ADAPTIVE_BANNER}
        requestOptions={{ requestNonPersonalizedAdsOnly: Platform.OS === "ios" }}
        onAdLoaded={() => recordAdImpression({
          placement, network: "admob", fmt: "display", tier, unit_id: bannerUnitId(),
        })}
        onAdOpened={() => recordAdClick({
          placement, network: "admob", fmt: "display", tier, unit_id: bannerUnitId(),
        })}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: "center",
    marginTop: 8,
    marginBottom: 4,
    minHeight: 50,
  },
});

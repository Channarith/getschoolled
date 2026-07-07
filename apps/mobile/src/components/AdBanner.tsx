import { useEffect, useState } from "react";
import { Platform, StyleSheet, View } from "react-native";

import { bannerUnitId, tierShowsAds } from "../ads/config";

type BannerModule = typeof import("react-native-google-mobile-ads");

let adsModule: BannerModule | null = null;
try {
  // Native module — requires dev client / EAS build (not Expo Go).
  adsModule = require("react-native-google-mobile-ads") as BannerModule;
} catch {
  adsModule = null;
}

type Props = {
  tier?: string;
};

/** Bottom banner for free/basic members. Uses Google test units in dev. */
export default function AdBanner({ tier }: Props) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!adsModule || !tierShowsAds(tier)) {
      return;
    }
    let cancelled = false;
    void adsModule.default()
      .initialize()
      .then(() => { if (!cancelled) setReady(true); })
      .catch(() => { /* simulator without Play Services */ });
    return () => { cancelled = true; };
  }, [tier]);

  if (!adsModule || !tierShowsAds(tier) || !ready) {
    return null;
  }

  const { BannerAd, BannerAdSize } = adsModule;
  return (
    <View style={styles.wrap} accessibilityLabel="Advertisement">
      <BannerAd
        unitId={bannerUnitId()}
        size={BannerAdSize.ANCHORED_ADAPTIVE_BANNER}
        requestOptions={{ requestNonPersonalizedAdsOnly: Platform.OS === "ios" }}
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

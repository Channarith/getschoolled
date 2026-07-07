declare module "react-native-google-mobile-ads" {
  import type { ComponentType } from "react";

  export const BannerAd: ComponentType<{
    unitId: string;
    size: string;
    requestOptions?: { requestNonPersonalizedAdsOnly?: boolean };
  }>;
  export const BannerAdSize: { ANCHORED_ADAPTIVE_BANNER: string };
  export const TestIds: { BANNER: string };

  export default function mobileAds(): {
    initialize(): Promise<void>;
  };
}

declare module "react-native-google-mobile-ads" {
  import type { ComponentType } from "react";

  export const BannerAd: ComponentType<{
    unitId: string;
    size: string;
    requestOptions?: { requestNonPersonalizedAdsOnly?: boolean };
    onAdLoaded?: () => void;
    onAdOpened?: () => void;
    onAdFailedToLoad?: (error: unknown) => void;
  }>;
  export const BannerAdSize: { ANCHORED_ADAPTIVE_BANNER: string };
  export const TestIds: { BANNER: string; INTERSTITIAL: string };

  export enum AdEventType {
    LOADED = "loaded",
    OPENED = "opened",
    CLOSED = "closed",
    ERROR = "error",
    CLICKED = "clicked",
  }

  export type RequestOptions = { requestNonPersonalizedAdsOnly?: boolean };

  export class InterstitialAd {
    static createForAdRequest(unitId: string, options?: RequestOptions): InterstitialAd;
    addAdEventListener(type: AdEventType, listener: (payload?: unknown) => void): () => void;
    load(): void;
    show(): void;
  }

  export default function mobileAds(): {
    initialize(): Promise<void>;
  };
}

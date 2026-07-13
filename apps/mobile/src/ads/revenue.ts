/** Mobile ad revenue beacons — mirror the web AdSlot/VideoAdBreak beacons.
 *
 * Best-effort POSTs to billing /ads/impression|/ads/click so AdMob banner +
 * interstitial views on iOS/Android feed the same in-app revenue ledger the
 * admin console reads. Real payout of record is AdMob's own dashboard; this is
 * our estimate + funnel. Never throws (fire-and-forget).
 */

import { Platform } from "react-native";

import { BILLING_URL } from "../api";

export type MobileAdBeacon = {
  placement: string;
  network?: string;
  fmt?: "display" | "video";
  tier?: string;
  unit_id?: string;
  creative_id?: string;
  advertiser?: string;
};

async function beacon(kind: "impression" | "click", ev: MobileAdBeacon): Promise<void> {
  try {
    await fetch(`${BILLING_URL}/ads/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        network: "admob",
        fmt: "display",
        advertiser: `AdMob (${Platform.OS})`,
        ...ev,
      }),
    });
  } catch {
    /* best-effort telemetry */
  }
}

export function recordAdImpression(ev: MobileAdBeacon): void {
  void beacon("impression", ev);
}

export function recordAdClick(ev: MobileAdBeacon): void {
  void beacon("click", ev);
}

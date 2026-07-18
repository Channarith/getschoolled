"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { getAdSlot, recordAdClick, recordAdImpression, type AdSlotPayload } from "../lib/api";
import { useFlag } from "../lib/flags";
import { effectiveAdTier } from "../lib/useCourseAds";

type Props = {
  slotId: string;
  tier: string;
  className?: string;
};

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

function AdSenseUnit({ slot, slotId, className }: {
  slot: AdSlotPayload;
  slotId: string;
  className?: string;
}) {
  useEffect(() => {
    if (!slot.client_id) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch {
      /* ad blockers / SSR */
    }
  }, [slot.client_id, slot.data_ad_slot]);

  return (
    <aside className={className} style={{ margin: "1rem 0", minHeight: slot.height || 90 }}>
      <ins
        className="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client={slot.client_id}
        data-ad-slot={slot.data_ad_slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
      {slot.script_url ? (
        <Script
          id={`adsense-${slotId}`}
          strategy="afterInteractive"
          src={slot.script_url}
          crossOrigin="anonymous"
        />
      ) : null}
      <p className="muted" style={{ fontSize: 11, marginTop: 4 }}>
        Ad — set ADSENSE_CLIENT in cloud env (use Google test publisher for staging)
      </p>
    </aside>
  );
}

/** Display ad slot for standard (non-VIP) members; VIP tiers see nothing.
 * Globally gated by the monetization.video_ads feature flag. */
export default function AdSlot({ slotId, tier, className }: Props) {
  const adsEnabled = useFlag<boolean>("monetization.video_ads", false);
  const [slot, setSlot] = useState<AdSlotPayload | null>(null);
  const logged = useRef(false);

  useEffect(() => {
    if (!adsEnabled) { setSlot({ show: false }); return; }
    let cancelled = false;
    logged.current = false;
    getAdSlot(slotId, effectiveAdTier(tier))
      .then((s) => { if (!cancelled) setSlot(s); })
      .catch(() => { if (!cancelled) setSlot({ show: false }); });
    return () => { cancelled = true; };
  }, [slotId, tier, adsEnabled]);

  // Impression beacon once, when a visible slot resolves.
  useEffect(() => {
    if (!slot?.show || logged.current) return;
    logged.current = true;
    recordAdImpression({
      placement: slotId, network: slot.network || "house", fmt: "display",
      tier: effectiveAdTier(tier), unit_id: slotId,
    });
  }, [slot, slotId, tier]);

  if (!adsEnabled || !slot?.show) return null;

  const onHouseClick = () => recordAdClick({
    placement: slotId, network: slot.network || "house", fmt: "display",
    tier: effectiveAdTier(tier), unit_id: slotId,
  });

  if (slot.house && slot.click_url) {
    return (
      <aside
        className={className}
        style={{
          margin: "1rem 0",
          padding: "12px 16px",
          borderRadius: 12,
          background: "linear-gradient(90deg, #1e293b, #0f172a)",
          border: "1px solid #334155",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <span style={{ fontSize: 14, color: "#e2e8f0" }}>{slot.label || "Sponsored"}</span>
        <a href={slot.click_url} onClick={onHouseClick} className="btn primary" style={{ fontSize: 13, padding: "6px 12px" }}>
          Learn more
        </a>
      </aside>
    );
  }

  if (slot.network === "google_adsense" && slot.client_id) {
    return <AdSenseUnit slot={slot} slotId={slotId} className={className} />;
  }

  return (
    <aside className={className} style={{ margin: "1rem 0", padding: 12, border: "1px dashed #475569", borderRadius: 8 }}>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>
        Ad slot ({slot.network}) — connect publisher credentials via AD_NETWORK env
      </p>
    </aside>
  );
}

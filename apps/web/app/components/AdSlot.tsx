"use client";

import { useEffect, useState } from "react";
import { getAdSlot, type AdSlotPayload } from "../lib/api";
import { useFlag } from "../lib/flags";

type Props = {
  slotId: string;
  tier: string;
  className?: string;
};

/** Display ad slot for standard (non-VIP) members; VIP tiers see nothing.
 * Globally gated by the monetization.video_ads feature flag. */
export default function AdSlot({ slotId, tier, className }: Props) {
  const adsEnabled = useFlag<boolean>("monetization.video_ads", true);
  const [slot, setSlot] = useState<AdSlotPayload | null>(null);

  useEffect(() => {
    if (!adsEnabled) { setSlot({ show: false }); return; }
    let cancelled = false;
    getAdSlot(slotId, tier)
      .then((s) => { if (!cancelled) setSlot(s); })
      .catch(() => { if (!cancelled) setSlot({ show: false }); });
    return () => { cancelled = true; };
  }, [slotId, tier, adsEnabled]);

  if (!adsEnabled || !slot?.show) return null;

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
        <a href={slot.click_url} className="btn primary" style={{ fontSize: 13, padding: "6px 12px" }}>
          Learn more
        </a>
      </aside>
    );
  }

  if (slot.network === "google_adsense" && slot.client_id) {
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
        <script
          async
          src={slot.script_url}
          crossOrigin="anonymous"
        />
        <p className="muted" style={{ fontSize: 11, marginTop: 4 }}>Ad — configure ADSENSE_CLIENT in cloud env</p>
      </aside>
    );
  }

  return (
    <aside className={className} style={{ margin: "1rem 0", padding: 12, border: "1px dashed #475569", borderRadius: 8 }}>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>
        Ad slot ({slot.network}) — connect publisher credentials via AD_NETWORK env
      </p>
    </aside>
  );
}

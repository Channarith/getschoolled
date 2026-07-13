"use client";

import { useEffect, useRef, useState } from "react";
import { recordAdClick, recordAdImpression, type AdBreak } from "../lib/api";

type Props = {
  adBreak: AdBreak;
  placement: string;          // e.g. "class-preroll", "watch-midroll", "drive-preroll"
  tier: string;
  network?: string;
  onDone: () => void;         // called on skip OR natural completion (resume content)
  mode?: "overlay" | "inline"; // overlay = fixed full-screen; inline = fill parent box
  audioOnly?: boolean;        // Drive Mode: compact card, no big video frame
};

/**
 * Plays a single ad break (pre/mid/post-roll) with a real <video> element,
 * a skip timer, click-through, and impression/click beacons for revenue
 * accounting. House inventory uses placeholder media URLs that won't load, so
 * the player gracefully falls back to a branded ad card with a countdown — the
 * ad still "runs" and is still counted. Swap in real creatives (or a VAST/IMA
 * tag) and the same component plays them.
 */
export default function VideoAdBreak({
  adBreak, placement, tier, network = "house", onDone, mode = "overlay", audioOnly = false,
}: Props) {
  const ad = adBreak.ads[0];
  const duration = ad?.duration_s ?? 15;
  const skipAfter = ad?.skippable_after_s ?? null;
  const [elapsed, setElapsed] = useState(0);
  const [useVideo, setUseVideo] = useState(!audioOnly);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const doneRef = useRef(false);

  // Impression beacon (once per break).
  useEffect(() => {
    if (!ad) { onDone(); return; }
    recordAdImpression({
      placement, network, fmt: "video", tier,
      unit_id: placement, creative_id: ad.id, advertiser: ad.advertiser,
    });
  }, [ad, placement, network, tier]); // eslint-disable-line react-hooks/exhaustive-deps

  const finish = () => { if (!doneRef.current) { doneRef.current = true; onDone(); } };

  // Fallback ticker (branded card / when the <video> can't load real media).
  useEffect(() => {
    if (useVideo) return;
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [useVideo]);
  useEffect(() => {
    if (!useVideo && elapsed >= duration) finish();
  }, [useVideo, elapsed, duration]); // eslint-disable-line react-hooks/exhaustive-deps

  const canSkip = skipAfter != null && elapsed >= skipAfter;
  const skipIn = skipAfter != null ? Math.max(0, skipAfter - elapsed) : 0;

  function onLearnMore() {
    if (ad?.click_url) {
      recordAdClick({
        placement, network, fmt: "video", tier,
        unit_id: placement, creative_id: ad.id, advertiser: ad.advertiser,
      });
      window.open(ad.click_url, "_blank", "noopener");
    }
  }

  if (!ad) return null;

  const card = (
    <div style={{ textAlign: "center", padding: 24, maxWidth: 560 }}>
      <div style={{ color: "#fbbf24", fontSize: 12, letterSpacing: 1, marginBottom: 8 }}>
        AD · {adBreak.position.toUpperCase()}
      </div>
      {useVideo ? (
        <video
          ref={videoRef}
          src={ad.media_url}
          autoPlay
          playsInline
          muted={false}
          onTimeUpdate={(e) => setElapsed(Math.floor(e.currentTarget.currentTime))}
          onEnded={finish}
          onError={() => setUseVideo(false)}
          style={{ width: "100%", maxHeight: audioOnly ? 0 : 320, borderRadius: 8, background: "#000" }}
        />
      ) : (
        <div style={{
          padding: audioOnly ? "18px 20px" : "40px 24px", borderRadius: 12,
          background: "linear-gradient(135deg,#1e293b,#0f172a)", border: "1px solid #334155",
        }}>
          <div style={{ fontSize: 22, color: "#fff", fontWeight: 600 }}>{ad.title}</div>
          <div style={{ color: "#93c5fd", marginTop: 6 }}>{ad.advertiser}</div>
        </div>
      )}
      <div style={{ color: "#aaa", marginTop: 10, fontSize: 13 }}>
        {ad.advertiser} · {elapsed}s / {duration}s
      </div>
      <div style={{ marginTop: 14, display: "flex", gap: 10, justifyContent: "center" }}>
        {ad.click_url && (
          <button onClick={onLearnMore} className="btn primary"
            style={{ padding: "8px 18px", cursor: "pointer" }}>
            Learn more
          </button>
        )}
        {canSkip ? (
          <button onClick={finish} aria-label="Skip ad"
            style={{ padding: "8px 18px", cursor: "pointer", background: "#334155", color: "#fff", border: 0, borderRadius: 6 }}>
            Skip ad →
          </button>
        ) : skipAfter != null ? (
          <span style={{ padding: "8px 12px", color: "#94a3b8", fontSize: 13 }}>Skip in {skipIn}s</span>
        ) : (
          <span style={{ padding: "8px 12px", color: "#94a3b8", fontSize: 13 }}>Ad plays in full</span>
        )}
      </div>
    </div>
  );

  if (mode === "inline") {
    return (
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center",
        justifyContent: "center", background: "rgba(0,0,0,0.92)", borderRadius: 12, zIndex: 5 }}
        role="dialog" aria-label="Advertisement">
        {card}
      </div>
    );
  }
  return (
    <div style={{ position: "fixed", inset: 0, display: "flex", alignItems: "center",
      justifyContent: "center", background: "rgba(0,0,0,0.9)", zIndex: 1000 }}
      role="dialog" aria-label="Advertisement">
      {card}
    </div>
  );
}

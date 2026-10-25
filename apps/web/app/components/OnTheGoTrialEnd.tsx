"use client";

import { useEffect, useRef } from "react";

/**
 * End of the anonymous On the Go demo: no price and no payment (nobody without an account can pay). The learner can create an account, log in,
 * or go back to the two-button landing page. The lesson, microphone and camera are already stopped by the player when this shows.
 */
export default function OnTheGoTrialEnd() {
  const firstRef = useRef<HTMLAnchorElement | null>(null);
  useEffect(() => { firstRef.current?.focus(); }, []);
  const next = encodeURIComponent("/drive");
  const link = {
    display: "inline-block", textAlign: "center", padding: "10px 16px", borderRadius: 12, fontWeight: 800, textDecoration: "none", fontSize: 15,
  } as const;
  return (
    <div
      role="dialog" aria-modal="true" aria-labelledby="otg-trial-end-title" data-testid="on-the-go-trial-end"
      style={{ position: "fixed", inset: 0, zIndex: 80, background: "rgba(5,8,20,.86)", display: "grid", placeItems: "center", padding: 16 }}
    >
      <div style={{ maxWidth: 420, width: "100%", background: "#0b1020", color: "#e8ecf6", borderRadius: 18, padding: 22, border: "2px solid #d4af37" }}>
        <h2 id="otg-trial-end-title" style={{ margin: "0 0 10px", fontSize: 21 }}>Create or log in to your account</h2>
        <p style={{ margin: "0 0 16px", fontSize: 15, lineHeight: 1.45 }}>
          Your free 10-minute demo has ended. Create an account or log in to your account to keep listening.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <a
            ref={firstRef} href={`/login?mode=signup&next=${next}`} data-testid="otg-trial-create"
            style={{ ...link, background: "#d4af37", color: "#0b1020", flex: 1 }}
          >Create account</a>
          <a
            href={`/login?next=${next}`} data-testid="otg-trial-login"
            style={{ ...link, background: "transparent", color: "#f4fbff", border: "1.5px solid rgba(212,175,55,.8)", flex: 1 }}
          >Log in</a>
        </div>
        <a
          href="/" data-testid="otg-trial-notnow"
          style={{ display: "block", marginTop: 14, textAlign: "center", color: "#9fbac2", fontSize: 14, textDecoration: "underline" }}
        >Not now</a>
      </div>
    </div>
  );
}

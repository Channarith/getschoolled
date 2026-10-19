"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "ready" | "down";

/**
 * Pre-flight the children-lab backend before mounting the iframe. When the
 * backend is unhealthy (deployment missing, ImagePullBackOff, crash) the
 * iframe would render a bare 500 page which looks broken and offers the
 * visitor no path forward. We instead probe /children-live-audio/health
 * (which Next rewrites to the children-lab backend's /health endpoint) and
 * fall back to a short "temporarily unavailable" card when it is not 2xx.
 *
 * The probe is only skipped when the iframe src points to a fully-qualified
 * external URL (NEXT_PUBLIC_CHILDREN_LAB_URL override) - in that case we have
 * no cross-origin health endpoint to safely hit, so we render the iframe and
 * let the browser show whatever the external origin returns.
 */
export function VisionArcadeFrame({ src, title }: { src: string; title: string }) {
  const sameOrigin = src.startsWith("/");
  const [status, setStatus] = useState<Status>(sameOrigin ? "checking" : "ready");

  useEffect(() => {
    if (!sameOrigin) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/children-live-audio/health", {
          method: "GET",
          cache: "no-store",
          // 4s is plenty for an in-cluster health endpoint; longer and we'd
          // leave the visitor staring at a blank iframe during an outage.
          signal: AbortSignal.timeout(4000),
        });
        if (cancelled) return;
        setStatus(r.ok ? "ready" : "down");
      } catch {
        if (!cancelled) setStatus("down");
      }
    })();
    return () => { cancelled = true; };
  }, [sameOrigin]);

  if (status === "down") {
    return (
      <div
        role="status"
        style={{
          width: "100%",
          minHeight: "min(60vh, 420px)",
          border: "1px solid rgba(165,180,252,.35)",
          borderRadius: 16,
          background: "#0f172a",
          color: "#e8ecf6",
          padding: "48px 24px",
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          gap: 14, textAlign: "center",
        }}
      >
        <h2 style={{ margin: 0, fontSize: 22 }}>Vision Play demo is warming up</h2>
        <p style={{ margin: 0, maxWidth: 560, color: "#cbd5e1" }}>
          The children-webcam service is briefly unreachable. It usually recovers in a minute
          or two after a deploy; please retry below. The rest of Salareen keeps working.
        </p>
        <button
          type="button"
          onClick={() => setStatus("checking")}
          style={{
            marginTop: 6, padding: "10px 20px", borderRadius: 10, border: 0, cursor: "pointer",
            background: "#0ea5e9", color: "#fff", fontWeight: 600,
          }}
        >
          Try again
        </button>
      </div>
    );
  }

  if (status === "checking") {
    return (
      <div
        aria-busy="true"
        style={{
          width: "100%",
          minHeight: "min(60vh, 420px)",
          border: "1px solid rgba(165,180,252,.35)",
          borderRadius: 16,
          background: "#0f172a",
          color: "#cbd5e1",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 15,
        }}
      >
        Loading Vision Play demo…
      </div>
    );
  }

  return (
    <iframe
      title={title}
      src={src}
      allow="camera; microphone; fullscreen"
      style={{
        width: "100%",
        height: "100%",
        minHeight: "min(88vh, 980px)",
        border: "1px solid rgba(165,180,252,.35)",
        borderRadius: 16,
        background: "#0f172a",
      }}
    />
  );
}

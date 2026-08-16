"use client";

import type { CSSProperties } from "react";
import {
  QUALITY_DISCONNECT_SECONDS,
  qualityDisconnectCopy,
  type LightingVerdict,
} from "../lib/cameraLighting";

type Props = {
  verdict: LightingVerdict;
  secondsLeft: number;
  onLeaveNow: () => void;
};

/**
 * Friendly mid-class overlay when lighting/blur makes recognition unreliable.
 * Counts down then the parent disconnects the learner.
 */
export default function CameraQualityGateOverlay({
  verdict,
  secondsLeft,
  onLeaveNow,
}: Props) {
  const copy = qualityDisconnectCopy(verdict);
  const panel: CSSProperties = {
    position: "fixed",
    inset: 0,
    zIndex: 80,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 20,
    background: "rgba(15, 23, 42, 0.72)",
    backdropFilter: "blur(6px)",
  };
  const card: CSSProperties = {
    maxWidth: 480,
    width: "100%",
    background: "var(--panel, #fff)",
    color: "var(--text, #111)",
    borderRadius: 16,
    border: "1px solid var(--border, #e5e7eb)",
    padding: "24px 22px",
    boxShadow: "0 18px 50px rgba(0,0,0,0.28)",
  };

  return (
    <div style={panel} role="alertdialog" aria-modal="true" aria-labelledby="cam-quality-title">
      <div style={card}>
        <p
          style={{
            margin: 0,
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: 0.04,
            textTransform: "uppercase",
            color: "#b45309",
          }}
        >
          Camera check required
        </p>
        <h2 id="cam-quality-title" style={{ margin: "8px 0 10px", fontSize: 22 }}>
          {copy.title}
        </h2>
        <p style={{ marginTop: 0, lineHeight: 1.45 }}>{copy.message}</p>
        <ul className="muted" style={{ marginTop: 0, paddingLeft: 18 }}>
          {copy.tips.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
        <p style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
          Leaving class in{" "}
          <span style={{ color: "#b91c1c", fontVariantNumeric: "tabular-nums" }}>
            {secondsLeft}
          </span>{" "}
          second{secondsLeft === 1 ? "" : "s"}
        </p>
        <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
          Fix lighting or focus, then rejoin. Default wait is {QUALITY_DISCONNECT_SECONDS}s.
        </p>
        <div className="row" style={{ gap: 8, marginTop: 14, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={onLeaveNow}
            style={{
              background: "#b91c1c",
              color: "#fff",
              border: "none",
              fontWeight: 700,
              padding: "10px 16px",
              borderRadius: 10,
              cursor: "pointer",
            }}
          >
            Leave now
          </button>
          <a href="/account/camera-check" style={{ alignSelf: "center", fontSize: 14 }}>
            Open camera check tool
          </a>
        </div>
      </div>
    </div>
  );
}

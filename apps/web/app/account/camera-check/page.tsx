"use client";

import CameraTrackingCheck from "../../components/CameraTrackingCheck";

export default function CameraCheckPage() {
  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "24px 16px 48px" }}>
      <p className="muted" style={{ marginBottom: 8 }}>
        <a href="/account">← Account</a>
      </p>
      <CameraTrackingCheck />
    </main>
  );
}

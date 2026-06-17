"use client";

import { useState } from "react";

export default function ConsentPage() {
  const [consent, setConsent] = useState(false);
  const [saved, setSaved] = useState(false);

  return (
    <main className="container">
      <h1>Biometric Consent</h1>
      <div className="card">
        <p>
          To recognize you across classes and measure attention, the platform
          processes camera frames using self-hosted vision models. Biometric data
          never leaves the configured boundary, is stored encrypted, and is
          deletable on request. This is opt-in, with a name-only fallback.
        </p>
        <label className="row">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => {
              setConsent(e.target.checked);
              setSaved(false);
            }}
          />
          <span>I consent to consent-gated vision features for my sessions.</span>
        </label>
        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={() => setSaved(true)}>Save preference</button>
          {saved && (
            <span className="muted">
              Saved: vision features are {consent ? "enabled" : "disabled"}.
            </span>
          )}
        </div>
      </div>
    </main>
  );
}

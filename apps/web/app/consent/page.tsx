"use client";

import { useState } from "react";

const SCOPES = [
  ["face_recognition", "Recognize me by face (opt-in; name-only otherwise)"],
  ["attention_tracking", "Estimate my attention/engagement"],
  ["recording", "Record this session"],
  ["cross_class_memory", "Remember me across classes"],
];

export default function ConsentPage() {
  const [granted, setGranted] = useState<Record<string, boolean>>({});

  return (
    <main>
      <div className="card">
        <h2>Consent &amp; privacy</h2>
        <p className="muted">
          Biometric features are off until you turn them on. Face embeddings are
          stored encrypted, never leave the configured boundary, and are
          deletable on request (FERPA / GDPR / BIPA).
        </p>
        {SCOPES.map(([scope, label]) => (
          <div key={scope} style={{ margin: "0.5rem 0" }}>
            <label>
              <input
                type="checkbox"
                checked={!!granted[scope]}
                onChange={(e) =>
                  setGranted((g) => ({ ...g, [scope]: e.target.checked }))
                }
              />
              &nbsp;{label}
            </label>
          </div>
        ))}
      </div>
    </main>
  );
}

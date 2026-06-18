"use client";

import { useState } from "react";
import { recordConsent } from "../lib/api";

const SCOPES: { id: string; label: string }[] = [
  { id: "face_recognition", label: "Face recognition (recognize me across classes)" },
  { id: "attention_tracking", label: "Attention/engagement tracking" },
  { id: "recording", label: "Session recording" },
  { id: "cross_class_memory", label: "Cross-class memory of my progress" },
];

export default function ConsentPage() {
  const [granted, setGranted] = useState<Record<string, boolean>>({});
  const [region, setRegion] = useState("us");
  const [written, setWritten] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  function toggle(id: string) {
    setGranted((g) => ({ ...g, [id]: !g[id] }));
    setStatus("");
  }

  async function onSave() {
    setError("");
    setStatus("");
    try {
      // Persist each scope decision to the memory consent API.
      for (const s of SCOPES) {
        await recordConsent({
          student_id: "current-user",
          scope: s.id,
          granted: Boolean(granted[s.id]),
          region,
          written,
        });
      }
      const enabled = SCOPES.filter((s) => granted[s.id]).map((s) => s.label);
      setStatus(
        enabled.length
          ? `Saved. Enabled: ${enabled.join("; ")}.`
          : "Saved. All optional vision/biometric features remain off."
      );
    } catch (e) {
      setError(String(e));
    }
  }

  const ilNeedsWritten = region === "us_il" || region === "eu";

  return (
    <main className="container">
      <h1>Biometric &amp; data consent</h1>
      <div className="card">
        <p>
          These features are <strong>opt-in</strong>, with a name-only fallback.
          Biometric data is processed by self-hosted vision models, never leaves
          the configured boundary, is stored encrypted, and is deletable on
          request. Your choices are recorded for audit and enforced by the
          per-region compliance policy. See the <a href="/legal">Legal</a> page.
        </p>

        <label className="row" style={{ marginBottom: 8 }}>
          Region&nbsp;
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="us">US (FERPA/COPPA)</option>
            <option value="us_il">US-IL (BIPA)</option>
            <option value="eu">EU (GDPR / EU AI Act)</option>
            <option value="other">Other</option>
          </select>
        </label>

        {SCOPES.map((s) => (
          <label className="row" key={s.id} style={{ display: "block", margin: "4px 0" }}>
            <input
              type="checkbox"
              checked={Boolean(granted[s.id])}
              onChange={() => toggle(s.id)}
            />
            &nbsp;<span>{s.label}</span>
          </label>
        ))}

        {ilNeedsWritten && (
          <label className="row" style={{ marginTop: 8 }}>
            <input type="checkbox" checked={written} onChange={(e) => setWritten(e.target.checked)} />
            &nbsp;<span>
              I provide written consent (required for biometrics in this region,
              e.g. BIPA / GDPR).
            </span>
          </label>
        )}

        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={onSave}>Save consent</button>
          {status && <span className="muted">{status}</span>}
        </div>
        {error && <p className="muted" style={{ color: "#ff6b6b" }}>{error}</p>}
      </div>
    </main>
  );
}

"use client";

import { useState } from "react";
import { verifyProvenance, type ProvenanceVerification } from "../lib/api";

export default function VerifyPage() {
  const [signed, setSigned] = useState("");
  const [content, setContent] = useState("");
  const [result, setResult] = useState<ProvenanceVerification | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onVerify() {
    setError("");
    setResult(null);
    setBusy(true);
    try {
      const parsed = JSON.parse(signed);
      const r = await verifyProvenance(parsed, content.trim() || undefined);
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <h1>Verify content credentials</h1>
      <p className="muted">
        Paste a signed content manifest (and optionally the original content) to
        check whether it is authentic and see its credentials: AI-generated?
        which model? human-reviewed? what sources?
      </p>

      <div className="card">
        <label>Signed manifest (JSON)</label>
        <textarea
          value={signed}
          onChange={(e) => setSigned(e.target.value)}
          rows={8}
          style={{ width: "100%", fontFamily: "monospace" }}
          placeholder='{"signature":"...","manifest":{...}}'
        />
        <label>Original content (optional, re-checks the hash)</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={3}
          style={{ width: "100%" }}
        />
        <div className="row" style={{ marginTop: 8 }}>
          <button onClick={onVerify} disabled={busy || !signed.trim()}>
            {busy ? "Verifying…" : "Verify"}
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">{error}</div>
        </div>
      )}

      {result && (
        <div
          className="card"
          style={{ borderColor: result.valid ? "#34d399" : "#ff6b6b" }}
        >
          <strong>{result.valid ? "Signature valid" : "Signature INVALID / tampered"}</strong>
          <div className="muted">Artifact: {result.artifact_id}</div>
          {result.content_matches !== null && (
            <div className="muted">
              Content hash matches: {String(result.content_matches)}
            </div>
          )}
          <ul>
            {result.assertions.map((a, i) => (
              <li key={i}>
                <code>{a.label}</code>: {JSON.stringify(a.data)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}

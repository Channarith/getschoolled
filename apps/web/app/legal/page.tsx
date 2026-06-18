"use client";

import { useEffect, useState } from "react";
import {
  acceptLegal,
  getCompliance,
  getLegalNotices,
  type LegalNotice,
} from "../lib/api";

export default function LegalPage() {
  const [notices, setNotices] = useState<LegalNotice[]>([]);
  const [required, setRequired] = useState<string[]>([]);
  const [region, setRegion] = useState("us");
  const [compliance, setCompliance] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getLegalNotices()
      .then((r) => {
        setNotices(r.notices);
        setRequired(r.required);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    getCompliance(region)
      .then(setCompliance)
      .catch(() => setCompliance(null));
  }, [region]);

  async function onAccept() {
    setError("");
    try {
      const r = await acceptLegal("current-user", required);
      setStatus(
        r.all_required_accepted
          ? "Thank you - your agreement to the Terms, Privacy Notice, and Acceptable Use Policy is recorded."
          : `Still outstanding: ${r.outstanding.join(", ")}`
      );
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <main className="container">
      <h1>Legal &amp; compliance</h1>
      <p className="muted">
        Use of this platform is licensed and must follow all applicable laws and
        the policies of your government, country, and institution. Review the
        notices below and record your agreement.
      </p>

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">{error}</div>
        </div>
      )}

      <div className="card">
        <h3>Notices</h3>
        <ul>
          {notices.map((n) => (
            <li key={n.id}>
              <strong>{n.title}</strong> (v{n.version})
              {required.includes(n.id) && <em> &mdash; required</em>}
              <div className="muted">{n.summary}</div>
              <div className="muted" style={{ fontSize: 12 }}>source: {n.path}</div>
            </li>
          ))}
        </ul>
        <button onClick={onAccept} disabled={notices.length === 0}>
          I agree to the required notices
        </button>
        {status && <p className="muted" style={{ marginTop: 8 }}>{status}</p>}
      </div>

      <div className="card">
        <h3>Region compliance</h3>
        <label>
          Region&nbsp;
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="us">US (FERPA/COPPA)</option>
            <option value="us_il">US-IL (BIPA)</option>
            <option value="eu">EU (GDPR / EU AI Act)</option>
            <option value="other">Other (baseline)</option>
          </select>
        </label>
        {compliance && (
          <ul>
            <li>Frameworks: {(compliance.frameworks as string[])?.join(", ")}</li>
            <li>Parental-consent age: {String(compliance.parental_consent_age)}</li>
            <li>Written biometric consent: {String(compliance.written_biometric_consent)}</li>
            <li>
              Emotion recognition allowed: {String(compliance.emotion_recognition_allowed)}
              {compliance.emotion_recognition_allowed === false && (
                <em> &mdash; disabled by law (e.g. EU AI Act)</em>
              )}
            </li>
            <li>AI high-risk (extra oversight): {String(compliance.ai_high_risk)}</li>
            <li>Default retention (days): {String(compliance.default_retention_days)}</li>
          </ul>
        )}
      </div>
    </main>
  );
}

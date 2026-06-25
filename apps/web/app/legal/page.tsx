"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getCompliance,
  getLegalNotices,
  acceptLegal,
  type LegalNotice,
} from "../lib/api";
import { useT } from "../lib/i18n";

export default function LegalPage() {
  const { t } = useT();
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
          ? t("legal.accepted")
          : t("legal.outstanding", { list: r.outstanding.join(", ") })
      );
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <main className="container">
      <h1>{t("legal.title")}</h1>
      <p className="muted">{t("legal.intro")}</p>

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">{error}</div>
        </div>
      )}

      <div className="card">
        <h3>{t("legal.notices")}</h3>
        <ul>
          {notices.map((n) => (
            <li key={n.id}>
              <strong>{n.title}</strong> (v{n.version})
              {required.includes(n.id) && <em> — {t("legal.required")}</em>}
              <div className="muted">{n.summary}</div>
              <div className="muted" style={{ fontSize: 12 }}>{t("legal.source")} {n.path}</div>
            </li>
          ))}
        </ul>
        <button onClick={onAccept} disabled={notices.length === 0}>
          {t("legal.agree")}
        </button>
        {status && <p className="muted" style={{ marginTop: 8 }}>{status}</p>}
      </div>

      <div className="card">
        <h3>{t("legal.regionCompliance")}</h3>
        <label>
          {t("legal.region")}&nbsp;
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="us">US (FERPA/COPPA)</option>
            <option value="us_il">US-IL (BIPA)</option>
            <option value="eu">EU (GDPR / EU AI Act)</option>
            <option value="other">Other (baseline)</option>
          </select>
        </label>
        {compliance && (
          <ul>
            <li>{t("legal.frameworks")} {(compliance.frameworks as string[])?.join(", ")}</li>
            <li>{t("legal.parentalAge")} {String(compliance.parental_consent_age)}</li>
            <li>{t("legal.writtenBio")} {String(compliance.written_biometric_consent)}</li>
            <li>
              {t("legal.emotionRec")} {String(compliance.emotion_recognition_allowed)}
              {compliance.emotion_recognition_allowed === false && (
                <em> — {t("legal.emotionDisabled")}</em>
              )}
            </li>
            <li>{t("legal.aiHighRisk")} {String(compliance.ai_high_risk)}</li>
            <li>{t("legal.retention")} {String(compliance.default_retention_days)}</li>
          </ul>
        )}
      </div>
    </main>
  );
}

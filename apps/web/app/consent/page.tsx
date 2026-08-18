"use client";

import { useState } from "react";
import Link from "next/link";
import { getToken, recordConsent } from "../lib/api";
import { useT } from "../lib/i18n";

const SCOPE_KEYS = [
  "face", "attention", "recording", "memory",
] as const;

export default function ConsentPage() {
  const { t } = useT();
  const [granted, setGranted] = useState<Record<string, boolean>>({});
  const [region, setRegion] = useState("us");
  const [written, setWritten] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const scopes = SCOPE_KEYS.map((id) => ({
    id: id === "face" ? "face_recognition"
      : id === "attention" ? "attention_tracking"
      : id === "recording" ? "recording"
      : "cross_class_memory",
    labelKey: `consent.scope.${id}` as const,
  }));

  function toggle(id: string) {
    setGranted((g) => ({ ...g, [id]: !g[id] }));
    setStatus("");
  }

  async function onSave() {
    setError("");
    setStatus("");
    if (!getToken()) {
      setError(t("consent.signInRequired"));
      return;
    }
    // Write all scopes in parallel; any failure is reported (a partial set is
    // still persisted server-side per scope, matching per-scope consent law).
    const results = await Promise.allSettled(
      scopes.map((s) =>
        recordConsent({
          scope: s.id,
          granted: Boolean(granted[s.id]),
          region,
          written,
        })
      )
    );
    const failed = results.filter((r) => r.status === "rejected");
    if (failed.length) {
      setError(String((failed[0] as PromiseRejectedResult).reason));
      return;
    }
    const enabled = scopes.filter((s) => granted[s.id]).map((s) => t(s.labelKey));
    setStatus(
      enabled.length
        ? t("consent.savedEnabled", { list: enabled.join("; ") })
        : t("consent.savedOff")
    );
  }

  const ilNeedsWritten = region === "us_il" || region === "eu";

  return (
    <main className="container">
      <h1>{t("consent.title")}</h1>
      <div className="card">
        <p>
          {t("consent.introBefore")}{" "}
          <Link href="/legal">{t("consent.legalLink")}</Link>{" "}
          {t("consent.introAfter")}
        </p>

        <label className="row" style={{ marginBottom: 8 }}>
          {t("legal.region")}&nbsp;
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="us">US (FERPA/COPPA)</option>
            <option value="us_il">US-IL (BIPA)</option>
            <option value="eu">EU (GDPR / EU AI Act)</option>
            <option value="other">Other</option>
          </select>
        </label>

        {scopes.map((s) => (
          <label className="row" key={s.id} style={{ display: "block", margin: "4px 0" }}>
            <input
              type="checkbox"
              checked={Boolean(granted[s.id])}
              onChange={() => toggle(s.id)}
            />
            &nbsp;<span>{t(s.labelKey)}</span>
          </label>
        ))}

        {ilNeedsWritten && (
          <label className="row" style={{ marginTop: 8 }}>
            <input type="checkbox" checked={written} onChange={(e) => setWritten(e.target.checked)} />
            &nbsp;<span>{t("consent.written")}</span>
          </label>
        )}

        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={onSave}>{t("consent.save")}</button>
          {status && <span className="muted">{status}</span>}
        </div>
        {error && <p className="muted" style={{ color: "#ff6b6b" }}>{error}</p>}
      </div>
    </main>
  );
}

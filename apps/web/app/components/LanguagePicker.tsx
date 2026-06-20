"use client";

import { useT } from "../lib/i18n";

// Simple inline language picker: native <select> so it works without
// any extra deps and integrates with the form-controls people are used
// to. The mobile app's flag-chip picker is fancier; web users expect a
// dropdown.
export default function LanguagePicker({
  compact = false,
}: { compact?: boolean }) {
  const { locale, setLocale, languages, t } = useT();
  return (
    <label
      style={{
        display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13,
      }}
      aria-label={t("lang.choose")}
    >
      {!compact && <span style={{ opacity: 0.8 }}>{t("lang.label")}:</span>}
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as typeof locale)}
        style={{
          background: "#111827", color: "#e8ecf6",
          border: "1px solid #1d2746", borderRadius: 6,
          padding: "4px 8px", fontSize: 13,
        }}
      >
        {languages.map((l) => (
          <option key={l.code} value={l.code}>
            {l.flag} {l.native}
          </option>
        ))}
      </select>
    </label>
  );
}

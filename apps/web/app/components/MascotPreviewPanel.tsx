"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getMascotCatalog,
  resolveMascot,
  type MascotCatalogEntry,
  type FlagSpec,
} from "../lib/api";
import { DEFAULT_MASCOT_SRC } from "../lib/mascot";
import MascotImage from "./MascotImage";

type Props = {
  flags: FlagSpec[];
  onPatch: (key: string, patch: { enabled?: boolean; value?: unknown }) => Promise<void>;
  busy: string;
};

/** Admin-only live preview + locale rotator for Bayon Buddy mascots. */
export default function MascotPreviewPanel({ flags, onPatch, busy }: Props) {
  const [catalog, setCatalog] = useState<MascotCatalogEntry[]>([]);
  const [idx, setIdx] = useState(0);
  const [resolved, setResolved] = useState<{ locale: string; path: string; theme: string } | null>(null);
  const [error, setError] = useState("");

  const enabledFlag = flags.find((f) => f.key === "ux.locale_mascots");
  const previewFlag = flags.find((f) => f.key === "ux.locale_mascots_preview_locale");
  const enabled = enabledFlag ? Boolean(enabledFlag.value) : true;
  const previewLocale = String(previewFlag?.value ?? "auto");

  useEffect(() => {
    getMascotCatalog()
      .then((r) => setCatalog(r.mascots))
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!catalog.length) return;
    const i = catalog.findIndex((m) => m.locale === previewLocale);
    if (i >= 0) setIdx(i);
  }, [catalog, previewLocale]);

  const refreshResolved = useCallback(async (locale: string) => {
    try {
      const r = await resolveMascot(locale);
      setResolved({
        locale: r.locale,
        path: r.path,
        theme: r.variant?.cultural_theme || "",
      });
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    if (!catalog.length) return;
    void refreshResolved(catalog[idx]?.locale || "en");
  }, [catalog, idx, enabled, previewLocale, refreshResolved]);

  async function rotate(delta: number) {
    if (!catalog.length) return;
    const next = (idx + delta + catalog.length) % catalog.length;
    setIdx(next);
    const loc = catalog[next].locale;
    setError("");
    await onPatch("ux.locale_mascots_preview_locale", { enabled: true, value: loc });
  }

  async function setAutoPreview() {
    setError("");
    await onPatch("ux.locale_mascots_preview_locale", { enabled: true, value: "auto" });
  }

  const current = catalog[idx];

  return (
    <section style={{ marginTop: 24 }}>
      <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
        Bayon Buddy · Locale Mascots
      </h2>
      <p style={{ fontSize: 13, color: "#666" }}>
        Preview the 27 culturally inspired mascot variants. Set a forced preview locale to test
        localization, or leave it on <code>auto</code> to follow each visitor&apos;s language.
        Toggle <code>ux.locale_mascots</code> below in UX Experiments to disable variants site-wide.
      </p>
      {error && <p style={{ color: "#b00", fontSize: 13 }}>{error}</p>}

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-start", marginTop: 12 }}>
        <div style={{ textAlign: "center", minWidth: 200 }}>
          <MascotImage width={180} alt="Locale mascot preview" />
          <p style={{ fontSize: 12, color: "#666", marginTop: 8 }}>
            {enabled ? "Localized mascots on" : "Localized mascots off (default mark)"}
          </p>
        </div>

        <div style={{ flex: "1 1 280px" }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
            <button type="button" disabled={!catalog.length || busy === "ux.locale_mascots_preview_locale"}
              onClick={() => rotate(-1)}
              style={{ padding: "6px 14px", cursor: "pointer" }}>
              ← Prev
            </button>
            <button type="button" disabled={!catalog.length || busy === "ux.locale_mascots_preview_locale"}
              onClick={() => rotate(1)}
              style={{ padding: "6px 14px", cursor: "pointer" }}>
              Next →
            </button>
            <button type="button" disabled={previewLocale === "auto" || busy === "ux.locale_mascots_preview_locale"}
              onClick={setAutoPreview}
              style={{ padding: "6px 14px", cursor: "pointer" }}>
              Reset to auto
            </button>
          </div>

          {current && (
            <div style={{ fontSize: 14, lineHeight: 1.5 }}>
              <div><strong>{current.locale.toUpperCase()}</strong> · {current.region}</div>
              <div style={{ color: "#444" }}>{current.cultural_theme}</div>
              <div style={{ fontSize: 12, color: "#666", marginTop: 6 }}>
                Preview flag: <code>{previewLocale}</code>
                {resolved && (
                  <> · resolved path: <code>{resolved.path || DEFAULT_MASCOT_SRC}</code></>
                )}
              </div>
            </div>
          )}

          {catalog.length > 0 && (
            <select
              value={previewLocale === "auto" ? current?.locale || "en" : previewLocale}
              onChange={(e) => onPatch("ux.locale_mascots_preview_locale", { enabled: true, value: e.target.value })}
              style={{ marginTop: 10, padding: 6, minWidth: 220 }}
            >
              {catalog.map((m) => (
                <option key={m.locale} value={m.locale}>
                  {m.locale.toUpperCase()} — {m.region}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
    </section>
  );
}

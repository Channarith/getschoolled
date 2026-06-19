"use client";

import { useEffect, useState } from "react";
import {
  adminListFlags,
  adminSetFlag,
  adminSurveyInsights,
  getServiceVersions,
  type FlagSpec,
  type ServiceVersion,
} from "../lib/api";
import { APP_VERSION } from "../lib/version";

type Insights = Awaited<ReturnType<typeof adminSurveyInsights>>;

const CATEGORY_LABELS: Record<string, string> = {
  engagement: "Engagement & Feedback",
  data: "Data & Data Mining",
  access: "Access & User Levels",
  monetization: "Monetization",
  ai: "AI Behavior",
  ux: "UX Experiments",
  ops: "Operations (kill-switches)",
};

export default function AdminPage() {
  const [secret, setSecret] = useState("");
  const [flags, setFlags] = useState<FlagSpec[]>([]);
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string>("");
  const [insights, setInsights] = useState<Insights | null>(null);
  const [versions, setVersions] = useState<ServiceVersion[] | null>(null);

  useEffect(() => {
    if (authed) getServiceVersions().then(setVersions).catch(() => setVersions([]));
  }, [authed]);

  async function load(s: string) {
    setError("");
    try {
      const f = await adminListFlags(s);
      setFlags(f);
      setAuthed(true);
    } catch (e) {
      setError("Invalid admin secret or memory service unavailable.");
      setAuthed(false);
      void e;
    }
  }

  async function loadInsights() {
    try {
      setInsights(await adminSurveyInsights(secret));
    } catch (e) {
      setError(`Could not load survey insights: ${String(e)}`);
    }
  }

  async function patch(key: string, p: Parameters<typeof adminSetFlag>[2]) {
    setBusy(key);
    try {
      const updated = await adminSetFlag(secret, key, p);
      setFlags((prev) => prev.map((f) => (f.key === key ? updated : f)));
    } catch (e) {
      setError(`Update failed for ${key}: ${String(e)}`);
    } finally {
      setBusy("");
    }
  }

  if (!authed) {
    return (
      <main style={{ maxWidth: 480, margin: "0 auto", padding: 24 }}>
        <h1>Admin · Feature Flags</h1>
        <p style={{ color: "#666" }}>
          Enter the administrative secret to manage platform feature flags.
        </p>
        <input
          type="password" placeholder="Admin secret" value={secret}
          onChange={(e) => setSecret(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(secret)}
          style={{ width: "100%", padding: 10, marginTop: 8 }}
        />
        <button onClick={() => load(secret)}
          style={{ marginTop: 12, padding: "8px 18px", background: "#111", color: "#fff", border: 0, borderRadius: 6, cursor: "pointer" }}>
          Unlock
        </button>
        {error && <p style={{ color: "#b00", marginTop: 10 }}>{error}</p>}
      </main>
    );
  }

  const byCat: Record<string, FlagSpec[]> = {};
  for (const f of flags) (byCat[f.category] ??= []).push(f);

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: 24 }}>
      <h1>Admin · Console</h1>
      <p style={{ color: "#666" }}>
        Toggle features, run percentage rollouts, target membership tiers. Changes apply immediately.
      </p>
      {error && <p style={{ color: "#b00" }}>{error}</p>}

      <section style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          System &amp; Versions
        </h2>
        <p style={{ fontSize: 13, color: "#666" }}>
          Web app <code>v{APP_VERSION}</code>. Each service also reports <code>/version</code> and
          a <code>/__meta</code> route index for automation.
        </p>
        {(() => {
          const reachable = (versions ?? []).filter((v) => v.reachable);
          const distinct = new Set(reachable.map((v) => v.version));
          return distinct.size > 1 ? (
            <p style={{ color: "#b45309" }}>⚠ Version mismatch across services: {[...distinct].join(", ")}</p>
          ) : reachable.length > 0 ? (
            <p style={{ color: "#16a34a" }}>✓ All reachable services on the same version.</p>
          ) : null;
        })()}
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
          <thead>
            <tr style={{ textAlign: "left", background: "#f7f7f7" }}>
              <th style={{ padding: 6 }}>Service</th><th style={{ padding: 6 }}>Status</th>
              <th style={{ padding: 6 }}>Version</th><th style={{ padding: 6 }}>API</th>
              <th style={{ padding: 6 }}>Mode</th><th style={{ padding: 6 }}>Git</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderTop: "1px solid #eee" }}>
              <td style={{ padding: 6 }}>web</td>
              <td style={{ padding: 6, color: "#16a34a" }}>● up</td>
              <td style={{ padding: 6 }}><code>{APP_VERSION}</code></td>
              <td style={{ padding: 6 }}>—</td><td style={{ padding: 6 }}>—</td><td style={{ padding: 6 }}>—</td>
            </tr>
            {(versions ?? []).map((v) => (
              <tr key={v.service} style={{ borderTop: "1px solid #eee" }}>
                <td style={{ padding: 6 }}>{v.service}</td>
                <td style={{ padding: 6, color: v.reachable ? "#16a34a" : "#b00" }}>
                  {v.reachable ? "● up" : "○ down"}
                </td>
                <td style={{ padding: 6 }}>{v.version ? <code>{v.version}</code> : "—"}</td>
                <td style={{ padding: 6 }}>{v.api_version ?? "—"}</td>
                <td style={{ padding: 6 }}>{v.deploy_mode ?? "—"}</td>
                <td style={{ padding: 6 }}>{v.git_sha || "—"}</td>
              </tr>
            ))}
            {versions === null && (
              <tr><td colSpan={6} style={{ padding: 6, color: "#666" }}>Loading service versions…</td></tr>
            )}
          </tbody>
        </table>
      </section>

      {Object.entries(byCat).map(([cat, items]) => (
        <section key={cat} style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
            {CATEGORY_LABELS[cat] ?? cat}
          </h2>
          {items.map((f) => (
            <div key={f.key} style={{ display: "flex", gap: 14, alignItems: "center",
              padding: "10px 0", borderBottom: "1px solid #f3f3f3", opacity: busy === f.key ? 0.5 : 1 }}>
              <div style={{ flex: 1 }}>
                <code style={{ fontWeight: 600 }}>{f.key}</code>
                {f.admin_only && <span style={{ marginLeft: 8, fontSize: 11, background: "#fee2e2",
                  color: "#991b1b", padding: "1px 6px", borderRadius: 4 }}>hidden</span>}
                <div style={{ fontSize: 13, color: "#666" }}>{f.description}</div>
              </div>

              {(f.type === "bool") && (
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input type="checkbox" checked={Boolean(f.value)}
                    onChange={(e) => patch(f.key, { enabled: true, value: e.target.checked })} />
                  {f.value ? "On" : "Off"}
                </label>
              )}

              {f.type === "percent" && (
                <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 180 }}>
                  <input type="range" min={0} max={100}
                    defaultValue={f.rollout_pct ?? Number(f.value) ?? 0}
                    onMouseUp={(e) => patch(f.key, { enabled: true, rollout_pct: Number((e.target as HTMLInputElement).value) })} />
                  <span style={{ fontSize: 12, width: 36 }}>{f.rollout_pct ?? f.value as number}%</span>
                </div>
              )}

              {f.type === "string" && (
                <select value={String(f.value)}
                  onChange={(e) => patch(f.key, { enabled: true, value: e.target.value })}
                  style={{ padding: 6 }}>
                  {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              )}

              {f.type === "int" && (
                <input type="number" defaultValue={Number(f.value)}
                  onBlur={(e) => patch(f.key, { enabled: true, value: Number(e.target.value) })}
                  style={{ width: 80, padding: 6 }} />
              )}
            </div>
          ))}
        </section>
      ))}

      <section style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          Survey Insights (multi-dimensional data mining)
        </h2>
        <button onClick={loadInsights}
          style={{ padding: "6px 14px", marginTop: 8, cursor: "pointer" }}>
          Load insights
        </button>
        {insights && (
          <div style={{ marginTop: 12 }}>
            <p>
              <strong>{insights.datamart.total_responses}</strong> responses ·
              data-mining flag: {insights.data_mining_enabled ? "on" : "off"}
            </p>
            <h4 style={{ marginBottom: 4 }}>By course × class type × rating</h4>
            <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
              <thead>
                <tr style={{ textAlign: "left", background: "#f7f7f7" }}>
                  <th style={{ padding: 6 }}>Course</th><th style={{ padding: 6 }}>Class type</th>
                  <th style={{ padding: 6 }}>Rating bucket</th><th style={{ padding: 6 }}>Responses</th>
                  <th style={{ padding: 6 }}>Avg</th>
                </tr>
              </thead>
              <tbody>
                {insights.datamart.cells.map((c, i) => (
                  <tr key={i} style={{ borderTop: "1px solid #eee" }}>
                    <td style={{ padding: 6 }}>{c.course_id}</td>
                    <td style={{ padding: 6 }}>{c.class_type}</td>
                    <td style={{ padding: 6 }}>{c.rating_bucket}</td>
                    <td style={{ padding: 6 }}>{c.responses}</td>
                    <td style={{ padding: 6 }}>{c.avg_overall}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {insights.datamart.top_suggestions.length > 0 && (
              <p style={{ marginTop: 10 }}>
                <strong>Mined suggestion themes:</strong>{" "}
                {insights.datamart.top_suggestions.map((t) => `${t.term} (${t.count})`).join(", ")}
              </p>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

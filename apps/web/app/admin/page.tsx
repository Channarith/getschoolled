"use client";

import { useState } from "react";
import { adminListFlags, adminSetFlag, type FlagSpec } from "../lib/api";

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
      <h1>Admin · Feature Flags</h1>
      <p style={{ color: "#666" }}>
        Toggle features, run percentage rollouts, target membership tiers. Changes apply immediately.
      </p>
      {error && <p style={{ color: "#b00" }}>{error}</p>}

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
    </main>
  );
}

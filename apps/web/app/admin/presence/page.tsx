"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getAdminPresence } from "../../lib/api";

const ACTIVITY_EMOJI: Record<string, string> = {
  "live-class": "📡", game: "🎮", language: "🌍", "drive-mode": "🚗",
  "group-class": "👥", kids: "🎓", corporate: "💼", browsing: "👀",
};

function timeAgo(ts: number): string {
  const s = Math.floor(Date.now() / 1000) - ts;
  if (s < 60) return s + "s ago";
  return Math.floor(s / 60) + "m ago";
}

export default function AdminPresencePage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getAdminPresence>> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await getAdminPresence());
      setError("");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <main className="container" style={{ maxWidth: 1000 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <Link href="/admin" style={{ color: "#6366f1", fontSize: 14 }}>{"← Admin"}</Link>
        <h1 style={{ margin: 0, fontSize: 24 }}>📡 Live User Presence</h1>
        <span style={{ marginLeft: "auto", fontSize: 13, color: "#64748b" }}>
          Auto-refreshes every 15s · {(data?.window_seconds ?? 300)}s window
        </span>
      </div>

      {error && <div className="card" style={{ borderColor: "#ff6b6b", color: "#b91c1c" }}>{error}</div>}
      {loading && !data && <div className="muted">Loading...</div>}

      {data && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16, marginBottom: 28 }}>
            <div className="card" style={{ textAlign: "center", background: "#f0f9ff" }}>
              <div style={{ fontSize: 40, fontWeight: 900, color: "#0369a1" }}>{data.active_count}</div>
              <div style={{ color: "#64748b", fontSize: 14 }}>Active users</div>
            </div>
            {Object.entries(data.by_platform).map(([plat, n]) => (
              <div key={plat} className="card" style={{ textAlign: "center" }}>
                <div style={{ fontSize: 32, fontWeight: 800 }}>{n}</div>
                <div style={{ color: "#64748b", fontSize: 13 }}>
                  {plat === "web" ? "🌐" : plat === "mobile" ? "📱" : "⚙️"} {plat}
                </div>
              </div>
            ))}
          </div>

          {Object.keys(data.by_activity).length > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <h3 style={{ marginTop: 0 }}>What they are doing</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                {Object.entries(data.by_activity).sort(([,a],[,b]) => b - a).map(([act, n]) => (
                  <div key={act} style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "8px 16px", fontSize: 14 }}>
                    {ACTIVITY_EMOJI[act] ?? "•"} {act} <strong>({n})</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Active sessions ({data.users.length})</h3>
            {data.users.length === 0 ? (
              <div className="muted">No active users in the last {data.window_seconds}s.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: "8px 12px" }}>User</th>
                    <th style={{ padding: "8px 12px" }}>Tier</th>
                    <th style={{ padding: "8px 12px" }}>Platform</th>
                    <th style={{ padding: "8px 12px" }}>Activity</th>
                    <th style={{ padding: "8px 12px" }}>Page</th>
                    <th style={{ padding: "8px 12px" }}>Last seen</th>
                  </tr>
                </thead>
                <tbody>
                  {data.users.map((u) => (
                    <tr key={u.account_id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "8px 12px", fontWeight: 600 }}>{u.display_name}</td>
                      <td style={{ padding: "8px 12px" }}><span style={{ fontSize: 11, background: "#f1f5f9", borderRadius: 6, padding: "2px 8px" }}>{u.tier}</span></td>
                      <td style={{ padding: "8px 12px" }}>{u.platform === "web" ? "🌐" : u.platform === "mobile" ? "📱" : "⚙️"} {u.platform}</td>
                      <td style={{ padding: "8px 12px" }}>{ACTIVITY_EMOJI[u.activity] ?? "•"} {u.activity}</td>
                      <td style={{ padding: "8px 12px", color: "#64748b", fontFamily: "monospace", fontSize: 12 }}>{u.page || "/"}</td>
                      <td style={{ padding: "8px 12px", color: "#94a3b8", fontSize: 12 }}>{timeAgo(u.seen_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </main>
  );
}

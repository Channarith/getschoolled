"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPortfolio, getToken, unsaveForLater, type Enrollment } from "../lib/api";
import SignInToUse from "../components/SignInToUse";

export default function MyListPage() {
  const [items, setItems] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    if (!getToken()) { setLoggedIn(false); setLoading(false); return; }
    getPortfolio()
      .then((p) => setItems(p.by_status?.saved ?? []))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function remove(courseId: string) {
    const prev = items;
    setItems((r) => r.filter((e) => e.course_id !== courseId));
    try {
      await unsaveForLater(courseId);
    } catch {
      setItems(prev); // revert optimistic removal on error
    }
  }

  if (!loggedIn) return <SignInToUse />;

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 20 }}>
        <h1 style={{ margin: 0 }}>🔖 Saved</h1>
        <span className="muted" style={{ fontSize: 14 }}>Courses you&apos;ve bookmarked for later</span>
        <Link href="/browse" style={{ marginLeft: "auto", fontSize: 14, color: "#0ea5e9" }}>
          + Browse more courses
        </Link>
      </div>

      {loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card" style={{ minHeight: 120, opacity: 0.4 }}>
              <div style={{ background: "var(--border)", borderRadius: 6, height: 18, width: "70%", marginBottom: 10 }} />
              <div style={{ background: "var(--border)", borderRadius: 6, height: 12, width: "50%" }} />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <p className="muted">{error}</p>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div style={{ textAlign: "center", padding: "60px 20px" }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>🔖</div>
          <h2>Your list is empty</h2>
          <p className="muted">
            Click the <strong>＋</strong> button on any course to save it here for later.
          </p>
          <Link href="/browse">
            <button style={{ background: "#0ea5e9", color: "#fff", padding: "12px 28px",
              fontSize: 16, borderRadius: 10, border: 0, cursor: "pointer", marginTop: 12 }}>
              Browse courses
            </button>
          </Link>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16 }}>
          {items.map((item) => (
            <div key={item.course_id} className="card" style={{ position: "relative", padding: 16 }}>
              {/* Remove button */}
              <button
                onClick={() => remove(item.course_id)}
                title="Remove from My List"
                style={{
                  position: "absolute", top: 10, right: 10,
                  background: "rgba(239,68,68,0.12)", border: "none", borderRadius: "50%",
                  width: 28, height: 28, cursor: "pointer", display: "flex",
                  alignItems: "center", justifyContent: "center", color: "#ef4444",
                  fontSize: 16, fontWeight: 700,
                }}
              >
                ×
              </button>

              <div style={{ paddingRight: 32 }}>
                <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6, lineHeight: 1.35 }}>
                  {item.title || item.course_id}
                </div>
                <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
                  Saved for later
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Link href={`/class?lesson=${encodeURIComponent(item.course_id)}`}>
                  <button style={{ background: "#0ea5e9", color: "#fff", padding: "8px 16px",
                    fontSize: 13, borderRadius: 8, border: 0, cursor: "pointer", fontWeight: 600 }}>
                    ▶ Start
                  </button>
                </Link>
                <Link href={`/drive?course=${encodeURIComponent(item.course_id)}`}>
                  <button style={{ background: "transparent", color: "#0ea5e9", padding: "8px 12px",
                    fontSize: 13, borderRadius: 8, border: "1px solid #0ea5e9", cursor: "pointer" }}>
                    🚗 Drive
                  </button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

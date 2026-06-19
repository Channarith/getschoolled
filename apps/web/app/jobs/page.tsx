"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  getJobMatch,
  listJobs,
  type JobMatch,
  type JobPosting,
} from "../lib/api";

const pretty = (s: string) => s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const SOURCE_ICON: Record<string, string> = { linkedin: "in", indeed: "Indeed", sample: "Board" };

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [source, setSource] = useState("");
  const [q, setQ] = useState("");
  const [loc, setLoc] = useState("");
  const [match, setMatch] = useState<JobMatch | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    listJobs(q || undefined, loc || undefined)
      .then((r) => { setJobs(r.jobs); setSource(r.source); })
      .catch((e) => setError(String(e)));
  }, [q, loc]);
  useEffect(() => { refresh(); }, [refresh]);

  async function openJob(id: string) {
    setError("");
    try { setMatch(await getJobMatch(id)); window.scrollTo({ top: 0, behavior: "smooth" }); }
    catch (e) { setError(String(e)); }
  }

  return (
    <main className="container" style={{ maxWidth: 1000 }}>
      <h1>💼 Careers — courses that get you hired</h1>
      <p className="muted">
        Real job openings matched to AI Classroom courses. See exactly which classes
        cover a role&rsquo;s skills, your coverage, and the gap to close.
        {source && source !== "sample" ? ` Live source: ${source}.`
          : " (Demo board representative of LinkedIn/Indeed; connect a provider with an API key for live listings.)"}
      </p>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {/* Job → courses match */}
      {match && (
        <div className="card" style={{ borderColor: "#0ea5e9" }}>
          <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
            <div>
              <h2 style={{ margin: 0 }}>{match.job.title}</h2>
              <div className="muted">{match.job.company} · {match.job.location} · {match.job.salary_range} · via {match.job.source}</div>
            </div>
            <button onClick={() => setMatch(null)}>✕ Close</button>
          </div>
          <p>{match.job.description}</p>

          <div style={{ margin: "10px 0" }}>
            <strong>You can cover {match.coverage_pct}% of this role with AI Classroom.</strong>
            <div style={{ height: 12, background: "#1d2746", borderRadius: 6, overflow: "hidden", marginTop: 6 }}>
              <div style={{ height: "100%", width: `${match.coverage_pct}%`,
                background: match.coverage_pct >= 75 ? "#16a34a" : "#0ea5e9" }} />
            </div>
          </div>

          <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
            {match.required.map((s) => (
              <span key={s} className="pill"
                style={{ color: match.covered.includes(s) ? "#16a34a" : "#b45309" }}>
                {match.covered.includes(s) ? "✓" : "•"} {pretty(s)}
              </span>
            ))}
          </div>

          <h3 style={{ marginBottom: 4 }}>Take these courses to qualify</h3>
          {match.matched_courses.length === 0 ? (
            <p className="muted">No matching courses yet.</p>
          ) : (
            <ul>
              {match.matched_courses.map((c) => (
                <li key={c.course_id} style={{ marginBottom: 4 }}>
                  <strong>{c.title}</strong>{" "}
                  <span className="muted" style={{ fontSize: 12 }}>
                    covers {c.covered_skills.map(pretty).join(", ")}
                  </span>
                  {match.recommended_path.includes(c.course_id) &&
                    <span className="pill" style={{ color: "#7c3aed", marginLeft: 6 }}>recommended</span>}
                </li>
              ))}
            </ul>
          )}
          {match.missing.length > 0 && (
            <p className="muted">Still to learn elsewhere: {match.missing.map(pretty).join(", ")}.</p>
          )}
          <div className="row" style={{ marginTop: 8 }}>
            <Link href="/browse"><button style={{ background: "#16a34a", color: "#fff" }}>Find these courses →</button></Link>
            <Link href="/drive"><button>Or learn on the drive</button></Link>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="card">
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Search roles / skills…" value={q} onChange={(e) => setQ(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: 10 }} />
          <input placeholder="Location" value={loc} onChange={(e) => setLoc(e.target.value)}
            style={{ width: 160, padding: 10 }} />
        </div>
      </div>

      {/* Openings */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px,1fr))", gap: 12 }}>
        {jobs.map((j) => (
          <button key={j.id} onClick={() => openJob(j.id)}
            style={{ textAlign: "left", background: "var(--panel)", color: "var(--text)",
              border: match?.job.id === j.id ? "2px solid #0ea5e9" : "1px solid var(--border)",
              borderRadius: 12, padding: 14, cursor: "pointer" }}>
            <div style={{ fontWeight: 700 }}>{j.title}</div>
            <div className="muted" style={{ fontSize: 12 }}>
              {j.company} · {j.location} · {j.salary_range}
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 4, marginTop: 6 }}>
              {j.skills.slice(0, 5).map((s) => (
                <span key={s} className="pill" style={{ fontSize: 10, color: "#9aa6c2" }}>{pretty(s)}</span>
              ))}
            </div>
            <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
              via {SOURCE_ICON[j.source] ?? j.source} · {j.posted_days_ago}d ago →
            </div>
          </button>
        ))}
        {jobs.length === 0 && <div className="muted">No openings match.</div>}
      </div>
    </main>
  );
}

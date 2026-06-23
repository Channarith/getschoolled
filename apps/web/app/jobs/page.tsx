"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  getJobMatch,
  listJobs,
  parseJobDescription,
  type JobMatch,
  type JobParse,
  type JobPosting,
} from "../lib/api";

const pretty = (s: string) => s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const SOURCE_ICON: Record<string, string> = {
  linkedin: "LinkedIn", indeed: "Indeed", glassdoor: "Glassdoor", ziprecruiter: "ZipRecruiter",
  remotive: "Remotive", arbeitnow: "Arbeitnow", adzuna: "Adzuna", jsearch: "JSearch",
  sample: "Demo board",
};

const SOURCE_BADGE: Record<string, { bg: string; fg: string }> = {
  linkedin: { bg: "#0a66c2", fg: "#ffffff" },
  indeed: { bg: "#2557a7", fg: "#ffffff" },
  glassdoor: { bg: "#0caa41", fg: "#ffffff" },
  ziprecruiter: { bg: "#1a7f37", fg: "#ffffff" },
  remotive: { bg: "#5b21b6", fg: "#ede9fe" },
  arbeitnow: { bg: "#334155", fg: "#e2e8f0" },
  adzuna: { bg: "#7c3aed", fg: "#ffffff" },
  sample: { bg: "#1e293b", fg: "#94a3b8" },
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [source, setSource] = useState("");
  const [q, setQ] = useState("");
  const [loc, setLoc] = useState("");
  const [match, setMatch] = useState<JobMatch | null>(null);
  const [jd, setJd] = useState("");
  const [parsed, setParsed] = useState<JobParse | null>(null);
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

  async function analyzeJd() {
    setError("");
    if (!jd.trim()) return;
    try { setParsed(await parseJobDescription(jd)); }
    catch (e) { setError(String(e)); }
  }

  return (
    <main className="container" style={{ maxWidth: 1000 }}>
      <h1>💼 Careers — courses that get you hired</h1>
      <p className="muted">
        Real job openings matched to Salareen courses. See exactly which classes
        cover a role&rsquo;s skills, your coverage, and the gap to close.
        {source && source !== "sample"
          ? ` Live openings from ${
              (Array.from(new Set(jobs.map((j) => j.source))).filter(Boolean) as string[])
                .map((s) => SOURCE_ICON[s] ?? pretty(s)).join(", ") || source
            } — click “View / Apply” to open the original posting.`
          : " (Showing a demo board while live sources are unavailable — set JOBS_LIVE=1, or a RAPIDAPI_KEY/Adzuna key for LinkedIn/Indeed-sourced listings.)"}
      </p>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {/* Job → courses match */}
      {match && (
        <div className="card" style={{ borderColor: "#0ea5e9" }}>
          <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
            <div>
              <h2 style={{ margin: 0 }}>{match.job.title}</h2>
              <div className="muted">
                {match.job.company} · {match.job.location} · {match.job.salary_range} · via {SOURCE_ICON[match.job.source] ?? match.job.source}
              </div>
              {match.job.url && (
                <a href={match.job.url} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: 13 }}>
                  View / Apply on {SOURCE_ICON[match.job.source] ?? match.job.source} ↗
                </a>
              )}
            </div>
            <button onClick={() => setMatch(null)}>✕ Close</button>
          </div>
          <p>{match.job.description}</p>

          <div style={{ margin: "10px 0" }}>
            <strong>You can cover {match.coverage_pct}% of this role with Salareen.</strong>
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

      {/* Paste a real (e.g. LinkedIn) job description -> targeted classes */}
      <div className="card" style={{ borderColor: "#7c3aed" }}>
        <h3 style={{ marginTop: 0 }}>🔎 Paste a job description (e.g. from LinkedIn)</h3>
        <p className="muted">We extract the exact skills + certifications and target specific classes — including cert prep like Cisco UCSM, AWS, PMP.</p>
        <textarea rows={4} value={jd} onChange={(e) => setJd(e.target.value)}
          placeholder="Paste the role's requirements here…"
          style={{ width: "100%", padding: 10 }} />
        <button onClick={analyzeJd} disabled={!jd.trim()}
          style={{ marginTop: 8, background: "#7c3aed", color: "#fff" }}>Analyze &amp; recommend</button>
        {parsed && (
          <div style={{ marginTop: 12 }}>
            {parsed.parsed.certifications.length > 0 && (
              <p><strong>Certifications detected:</strong>{" "}
                {parsed.parsed.certifications.map((c) => (
                  <span key={c} className="pill" style={{ color: "#7c3aed" }}>{c}</span>
                ))}</p>
            )}
            <p><strong>Skills:</strong> {parsed.parsed.skills.map(pretty).join(", ") || "—"}</p>
            <p>Catalog coverage: <strong>{parsed.coverage_pct}%</strong></p>
            {parsed.matched_courses.length > 0 && (
              <>
                <div style={{ fontWeight: 600 }}>Take these courses:</div>
                <ul>{parsed.matched_courses.map((c) => (
                  <li key={c.course_id}>{c.title} <span className="muted" style={{ fontSize: 12 }}>
                    ({c.covered_skills.map(pretty).join(", ")})</span></li>
                ))}</ul>
              </>
            )}
            {parsed.specialized_classes.length > 0 && (
              <>
                <div style={{ fontWeight: 600 }}>Specialized classes to add (targeted to this role):</div>
                <ul>{parsed.specialized_classes.map((s, i) => (
                  <li key={i}>
                    {s.title}{" "}
                    <span className="pill" style={{ color: s.kind === "certification" ? "#16a34a" : "#b45309" }}>
                      {s.kind}
                    </span>
                  </li>
                ))}</ul>
              </>
            )}
          </div>
        )}
      </div>

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
      <div className="job-grid">
        {jobs.map((j) => {
          const badge = SOURCE_BADGE[j.source] ?? { bg: "#1e293b", fg: "#cbd5e1" };
          return (
          <div key={j.id} role="button" tabIndex={0} onClick={() => openJob(j.id)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openJob(j.id); } }}
            className={`job-card${match?.job.id === j.id ? " selected" : ""}`}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
              <div className="job-title">{j.title}</div>
              <span className="source-badge" style={{ background: badge.bg, color: badge.fg }}>
                {SOURCE_ICON[j.source] ?? pretty(j.source)}
              </span>
            </div>
            <div className="job-meta">
              {j.company}{j.location ? ` · ${j.location}` : ""}{j.salary_range ? ` · ${j.salary_range}` : ""}
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 4 }}>
              {j.skills.slice(0, 5).map((s) => (
                <span key={s} className="pill" style={{ fontSize: 10, color: "var(--accent)" }}>{pretty(s)}</span>
              ))}
            </div>
            <div className="job-foot">
              <span className="muted" style={{ fontSize: 11 }}>
                {j.posted_days_ago ? `${j.posted_days_ago}d ago` : "recently"} · tap for course match →
              </span>
              {j.url && (
                <a href={j.url} target="_blank" rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  style={{ fontSize: 11 }}>
                  View / Apply ↗
                </a>
              )}
            </div>
          </div>
          );
        })}
        {jobs.length === 0 && <div className="muted">No openings match.</div>}
      </div>
    </main>
  );
}

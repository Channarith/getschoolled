"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  getJobMatch, listJobs, parseJobDescription,
  type JobMatch, type JobParse, type JobPosting,
} from "../lib/api";
import { useT } from "../lib/i18n";

const pretty = (s: string) => s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function excerpt(text: string, max = 140): string {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  return `${flat.slice(0, max).trim()}…`;
}
const SOURCE_ICON: Record<string, string> = {
  linkedin: "LinkedIn", indeed: "Indeed", glassdoor: "Glassdoor", ziprecruiter: "ZipRecruiter",
  remotive: "Remotive", arbeitnow: "Arbeitnow", remoteok: "RemoteOK",
  adzuna: "Adzuna", jsearch: "JSearch", sample: "Demo board",
};

const SOURCE_BADGE: Record<string, { bg: string; fg: string }> = {
  linkedin: { bg: "#0a66c2", fg: "#ffffff" },
  indeed: { bg: "#2557a7", fg: "#ffffff" },
  glassdoor: { bg: "#0caa41", fg: "#ffffff" },
  ziprecruiter: { bg: "#1a7f37", fg: "#ffffff" },
  remotive: { bg: "#5b21b6", fg: "#ede9fe" },
  arbeitnow: { bg: "#334155", fg: "#e2e8f0" },
  remoteok: { bg: "#1d4ed8", fg: "#ffffff" },
  adzuna: { bg: "#7c3aed", fg: "#ffffff" },
  sample: { bg: "#1e293b", fg: "#94a3b8" },
};

/** Build a search URL for each major job platform using the active query/location. */
function platformSearchUrl(platform: string, q: string, loc: string): string {
  const eq = encodeURIComponent(q || "software engineer");
  const el = encodeURIComponent(loc || "");
  switch (platform) {
    case "linkedin":
      return `https://www.linkedin.com/jobs/search/?keywords=${eq}${el ? `&location=${el}` : ""}`;
    case "indeed":
      return `https://www.indeed.com/jobs?q=${eq}${el ? `&l=${el}` : ""}`;
    case "glassdoor":
      return `https://www.glassdoor.com/Job/jobs.htm?sc.keyword=${eq}${el ? `&locT=C&locId=0&locKeyword=${el}` : ""}`;
    case "ziprecruiter":
      return `https://www.ziprecruiter.com/jobs-search?search=${eq}${el ? `&location=${el}` : ""}`;
    default:
      return "#";
  }
}

const EXTERNAL_PLATFORMS = [
  { key: "linkedin",     label: "LinkedIn",     color: "#0a66c2", emoji: "💼" },
  { key: "indeed",       label: "Indeed",       color: "#2557a7", emoji: "🔍" },
  { key: "ziprecruiter", label: "ZipRecruiter", color: "#1a7f37", emoji: "⚡" },
  { key: "glassdoor",    label: "Glassdoor",    color: "#0caa41", emoji: "🚪" },
];

export default function JobsPage() {
  const { t } = useT();
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [loc, setLoc] = useState("");
  const [match, setMatch] = useState<JobMatch | null>(null);
  const [jd, setJd] = useState("");
  const [parsed, setParsed] = useState<JobParse | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    setLoading(true);
    setError("");
    listJobs(q || undefined, loc || undefined)
      .then((r) => { setJobs(r.jobs); setSource(r.source); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
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
      <h1>{t("jobs.title")}</h1>
      <p className="muted">
        {t("jobs.intro")}
        {source && source !== "sample"
          ? t("jobs.liveSources", {
              sources: (Array.from(new Set(jobs.map((j) => j.source))).filter(Boolean) as string[])
                .map((s) => SOURCE_ICON[s] ?? pretty(s)).join(", ") || source,
            })
          : t("jobs.demoBoard")}
      </p>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {/* Work AT Salareen (distinct from the external job board below). */}
      <div className="card" style={{ borderColor: "#7c3aed", display: "flex", justifyContent: "space-between",
        alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div>
          <strong>Want to work at Salareen?</strong>
          <div className="muted" style={{ fontSize: 13 }}>
            We&apos;re building the agentic education platform. Send your résumé and what you&apos;d love to build.
          </div>
        </div>
        <a href="mailto:jobs@salareen.com?subject=Careers%20—%20I%27d%20like%20to%20join%20Salareen">
          <button style={{ background: "#7c3aed", color: "#fff" }}>💼 jobs@salareen.com</button>
        </a>
      </div>

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
                  {t("jobs.viewApply", { source: SOURCE_ICON[match.job.source] ?? match.job.source })}
                </a>
              )}
            </div>
            <button onClick={() => setMatch(null)}>{t("jobs.close")}</button>
          </div>
          <p className="job-description">{match.job.description}</p>

          <div style={{ margin: "10px 0" }}>
            <strong>{t("jobs.coverage", { pct: match.coverage_pct })}</strong>
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

          <h3 style={{ marginBottom: 4 }}>{t("jobs.takeCourses")}</h3>
          {match.matched_courses.length === 0 ? (
            <p className="muted">{t("jobs.noMatchCourses")}</p>
          ) : (
            <ul>
              {match.matched_courses.map((c) => (
                <li key={c.course_id} style={{ marginBottom: 4 }}>
                  <strong>{c.title}</strong>{" "}
                  <span className="muted" style={{ fontSize: 12 }}>
                    {t("jobs.covers", { skills: c.covered_skills.map(pretty).join(", ") })}
                  </span>
                  {match.recommended_path.includes(c.course_id) &&
                    <span className="pill" style={{ color: "#7c3aed", marginLeft: 6 }}>{t("jobs.recommended")}</span>}
                </li>
              ))}
            </ul>
          )}
          {match.missing.length > 0 && (
            <p className="muted">{t("jobs.stillLearn", { skills: match.missing.map(pretty).join(", ") })}</p>
          )}
          <div className="row" style={{ marginTop: 8 }}>
            <Link href="/browse"><button style={{ background: "#16a34a", color: "#fff" }}>{t("jobs.findCourses")}</button></Link>
            <Link href="/drive"><button>{t("jobs.learnDrive")}</button></Link>
          </div>
        </div>
      )}

      {/* Paste a real (e.g. LinkedIn) job description -> targeted classes */}
      <div className="card" style={{ borderColor: "#7c3aed" }}>
        <h3 style={{ marginTop: 0 }}>{t("jobs.pasteTitle")}</h3>
        <p className="muted">{t("jobs.pasteDesc")}</p>
        <textarea rows={4} value={jd} onChange={(e) => setJd(e.target.value)}
          placeholder={t("jobs.pastePlaceholder")}
          style={{ width: "100%", padding: 10 }} />
        <button onClick={analyzeJd} disabled={!jd.trim()}
          style={{ marginTop: 8, background: "#7c3aed", color: "#fff" }}>{t("jobs.analyze")}</button>
        {parsed && (
          <div style={{ marginTop: 12 }}>
            {parsed.parsed.certifications.length > 0 && (
              <p><strong>{t("jobs.certsDetected")}</strong>{" "}
                {parsed.parsed.certifications.map((c) => (
                  <span key={c} className="pill" style={{ color: "#7c3aed" }}>{c}</span>
                ))}</p>
            )}
            <p><strong>{t("jobs.skillsLabel")}</strong> {parsed.parsed.skills.map(pretty).join(", ") || "—"}</p>
            <p>{t("jobs.catalogCoverage")} <strong>{parsed.coverage_pct}%</strong></p>
            {parsed.matched_courses.length > 0 && (
              <>
                <div style={{ fontWeight: 600 }}>{t("jobs.takeThese")}</div>
                <ul>{parsed.matched_courses.map((c) => (
                  <li key={c.course_id}>{c.title} <span className="muted" style={{ fontSize: 12 }}>
                    ({c.covered_skills.map(pretty).join(", ")})</span></li>
                ))}</ul>
              </>
            )}
            {parsed.specialized_classes.length > 0 && (
              <>
                <div style={{ fontWeight: 600 }}>{t("jobs.specialized")}</div>
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
        <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder={t("jobs.searchRoles")} value={q} onChange={(e) => setQ(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: 10 }} />
          <input placeholder={t("jobs.location")} value={loc} onChange={(e) => setLoc(e.target.value)}
            style={{ width: 160, padding: 10 }} />
          <button type="button" onClick={refresh} disabled={loading}
            style={{ background: "#16a34a", color: "#fff", padding: "10px 16px" }}>
            {loading ? t("jobs.searching") : t("jobs.search")}
          </button>
        </div>
        {!loading && jobs.length > 0 && (
          <p className="muted" style={{ margin: "10px 0 0", fontSize: 13 }}>
            {jobs.length === 1
              ? t("jobs.openings", { n: jobs.length })
              : t("jobs.openingsPlural", { n: jobs.length })}
            {source ? ` · ${SOURCE_ICON[source] ?? pretty(source)}` : ""}
          </p>
        )}
      </div>

      {/* Search directly on major platforms */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", margin: "4px 0 8px" }}>
        <span className="muted" style={{ fontSize: 13, whiteSpace: "nowrap" }}>Also search on:</span>
        {EXTERNAL_PLATFORMS.map(({ key, label, color, emoji }) => (
          <a
            key={key}
            href={platformSearchUrl(key, q, loc)}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex", alignItems: "center", gap: 5,
              padding: "6px 14px", borderRadius: 20, fontSize: 13, fontWeight: 600,
              background: color, color: "#fff", textDecoration: "none",
              boxShadow: "0 1px 3px rgba(0,0,0,.15)",
            }}
          >
            {emoji} {label}
          </a>
        ))}
      </div>

      {loading && (
        <div className="job-grid" aria-busy="true" aria-label={t("jobs.loading")}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="job-card job-card-skeleton" aria-hidden="true">
              <div className="skeleton-line" style={{ width: "70%", height: 18 }} />
              <div className="skeleton-line" style={{ width: "50%", height: 14 }} />
              <div className="skeleton-line" style={{ width: "90%", height: 12 }} />
            </div>
          ))}
        </div>
      )}

      {/* Openings */}
      {!loading && (
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
            {(j.employment_type || j.category) && (
              <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                {j.employment_type && (
                  <span className="pill" style={{ fontSize: 10, color: "#16a34a" }}>{j.employment_type}</span>
                )}
                {j.category && (
                  <span className="pill" style={{ fontSize: 10, color: "var(--muted)" }}>{j.category}</span>
                )}
              </div>
            )}
            {j.description && (
              <p className="job-blurb">{excerpt(j.description)}</p>
            )}
            <div className="row" style={{ flexWrap: "wrap", gap: 4 }}>
              {j.skills.slice(0, 5).map((s) => (
                <span key={s} className="pill" style={{ fontSize: 10, color: "var(--accent)" }}>{pretty(s)}</span>
              ))}
            </div>
            <div className="job-foot">
              <span className="muted" style={{ fontSize: 11 }}>
                {j.posted_days_ago
                  ? t("jobs.daysAgo", { n: j.posted_days_ago })
                  : t("jobs.recently")} · {t("jobs.tapMatch")}
              </span>
              {j.url && (
                <a href={j.url} target="_blank" rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  style={{ fontSize: 11 }}>
                  {t("jobs.viewApplyShort")}
                </a>
              )}
            </div>
          </div>
          );
        })}
        {jobs.length === 0 && <div className="muted card">{t("jobs.noResults")}</div>}
      </div>
      )}
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  enrollCourse,
  getFacets,
  getToken,
  searchCourses,
  type CatalogCourse,
  type Facets,
} from "../lib/api";

export default function BrowsePage() {
  const [facets, setFacets] = useState<Facets | null>(null);
  const [courses, setCourses] = useState<CatalogCourse[]>([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({
    q: "", category: "", language: "", audio: "", media_format: "", level: "", hands_on: "",
    audience: "", core_skill: "",
  });

  useEffect(() => {
    getFacets().then(setFacets).catch(() => setFacets(null));
  }, []);

  useEffect(() => {
    searchCourses(filters).then(setCourses).catch((e) => setError(String(e)));
  }, [filters]);

  function set(key: string, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
  }

  async function onEnroll(c: CatalogCourse) {
    setMsg("");
    if (!getToken()) {
      setMsg("Please sign in to enroll.");
      return;
    }
    try {
      await enrollCourse(c.course_id, c.title);
      setMsg(`Enrolled in "${c.title}". See it in your Account.`);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <main className="container">
      <h1>Browse courses</h1>
      <p className="muted">
        Preview and enroll. Search by name and filter by category, language, audio,
        format, level, and hands-on. {!getToken() && <Link href="/login">Sign in</Link>} to build your portfolio.
      </p>

      <div className="card">
        <input
          placeholder="Search courses…"
          value={filters.q}
          onChange={(e) => set("q", e.target.value)}
          style={{ width: "100%", padding: 8, marginBottom: 8 }}
        />
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          <Facet label="Category" value={filters.category} onChange={(v) => set("category", v)} options={facets?.categories} />
          <Facet label="Language" value={filters.language} onChange={(v) => set("language", v)} options={facets?.languages} />
          <Facet label="Audio" value={filters.audio} onChange={(v) => set("audio", v)} options={facets?.audio_languages} />
          <Facet label="Format" value={filters.media_format} onChange={(v) => set("media_format", v)} options={facets?.media_formats} />
          <Facet label="Level" value={filters.level} onChange={(v) => set("level", v)} options={facets?.levels} />
          <label style={{ fontSize: 13 }}>
            For&nbsp;
            <select value={filters.audience} onChange={(e) => set("audience", e.target.value)}>
              <option value="">Anyone</option>
              {(facets?.audiences ?? []).map((a) => (
                <option key={a.slug} value={a.slug}>{a.label}</option>
              ))}
            </select>
          </label>
          <label className="row">
            <input type="checkbox" checked={filters.hands_on === "true"}
              onChange={(e) => set("hands_on", e.target.checked ? "true" : "")} />
            &nbsp;Hands-on only
          </label>
          <label className="row">
            <input type="checkbox" checked={filters.core_skill === "true"}
              onChange={(e) => set("core_skill", e.target.checked ? "true" : "")} />
            &nbsp;Core skills
          </label>
        </div>
      </div>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}
      {msg && <div className="card" style={{ borderColor: "#34d399" }}><div className="muted">{msg}</div></div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
        {courses.length === 0 && <div className="muted">No courses match these filters.</div>}
        {courses.map((c) => (
          <div className="card" key={c.course_id}>
            <h3 style={{ marginBottom: 4 }}>{c.title}</h3>
            <div className="muted" style={{ fontSize: 12 }}>
              {c.category} · {c.language}
              {c.audio_language && c.audio_language !== c.language ? ` · audio ${c.audio_language}` : ""}
              {" · "}{c.media_format} · {c.level}
            </div>
            {c.hands_on && (
              <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 999, border: "1px solid #f59e0b", color: "#b45309" }}>
                Hands-on training
              </span>
            )}
            <p className="muted" style={{ marginTop: 6 }}>{c.preview || c.description}</p>
            <div className="row" style={{ marginTop: 8, gap: 8 }}>
              <button onClick={() => onEnroll(c)}>Enroll</button>
              <span className="muted" style={{ fontSize: 12, alignSelf: "center" }}>
                {c.access_tier !== "free" ? `${c.access_tier} plan` : "free"}
              </span>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

function Facet({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options?: string[];
}) {
  return (
    <label style={{ fontSize: 13 }}>
      {label}&nbsp;
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Any</option>
        {(options ?? []).map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

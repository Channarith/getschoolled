"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  enrollCourse,
  getLearnFacets,
  getToken,
  searchLearnable,
  type Facets,
  type LearnableItem,
} from "../lib/api";
import { coursePosterUrl } from "../lib/courseArtwork";

const FORMAT_LABELS: Record<string, string> = {
  audio: "Audio / Drive",
  live_class: "Live class",
  interactive: "Interactive",
  game: "Arcade",
  program: "Program",
  video: "Video",
};

const SOURCE_LABELS: Record<string, string> = {
  audio: "Drive catalog",
  lesson: "Live lessons",
  language: "Languages",
  catalog: "Catalog",
  game: "Arcade",
  program: "Programs",
};

export default function BrowsePage() {
  const router = useRouter();
  const [loggedIn, setLoggedIn] = useState(false);
  const [authResolved, setAuthResolved] = useState(false);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [items, setItems] = useState<LearnableItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({
    q: "", category: "", language: "", format: "", source: "", level: "",
    hands_on: "", audience: "", core_skill: "",
  });

  useEffect(() => {
    const authed = Boolean(getToken());
    setLoggedIn(authed);
    setAuthResolved(true);
    if (!authed) return;
    getLearnFacets().then(setFacets).catch(() => setFacets(null));
  }, []);

  useEffect(() => {
    if (!loggedIn) return;
    searchLearnable({ ...filters, limit: "80" })
      .then((r) => { setItems(r.items); setTotal(r.total); })
      .catch((e) => setError(String(e)));
  }, [filters, loggedIn]);

  function set(key: string, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
  }

  function openItem(item: LearnableItem) {
    if (item.deep_link) {
      router.push(item.deep_link);
      return;
    }
    if (item.format === "audio") {
      router.push(`/drive?course=${encodeURIComponent(item.source_id)}`);
    }
  }

  async function onEnroll(item: LearnableItem) {
    setMsg("");
    if (!getToken()) {
      setMsg("Please sign in to enroll.");
      return;
    }
    if (item.source !== "catalog") {
      openItem(item);
      return;
    }
    try {
      await enrollCourse(item.source_id, item.title);
      setMsg(`Enrolled in "${item.title}". See it in your Account.`);
    } catch (e) {
      setError(String(e));
    }
  }

  if (!authResolved) {
    return (
      <main className="container">
        <p className="muted">Loading…</p>
      </main>
    );
  }

  if (!loggedIn) {
    return (
      <main className="container">
        <h1>Browse all learning</h1>
        <div className="card">
          <p>
            Please <Link href="/login">sign in</Link> to browse the full catalog of live classes,
            drive-safe audio, languages, arcade games, and courses.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <h1>Browse all learning</h1>
      <p className="muted">
        Search across live classes, drive-safe audio, languages, arcade games, and catalog courses.
      </p>

      <div className="card">
        <input
          placeholder="Search everything…"
          value={filters.q}
          onChange={(e) => set("q", e.target.value)}
          style={{ width: "100%", padding: 8, marginBottom: 8 }}
        />
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          <Facet label="Category" value={filters.category} onChange={(v) => set("category", v)} options={facets?.categories} />
          <Facet label="Type" value={filters.format} onChange={(v) => set("format", v)}
            options={facets?.formats?.map((f) => FORMAT_LABELS[f] ? `${f}` : f)}
            optionValues={facets?.formats}
            formatLabels={FORMAT_LABELS} />
          <Facet label="Source" value={filters.source} onChange={(v) => set("source", v)}
            options={facets?.sources?.map((s) => SOURCE_LABELS[s] || s)}
            optionValues={facets?.sources} />
          <Facet label="Language" value={filters.language} onChange={(v) => set("language", v)} options={facets?.languages} />
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
        </div>
      </div>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}
      {msg && <div className="card" style={{ borderColor: "#34d399" }}><div className="muted">{msg}</div></div>}

      <p className="muted" style={{ marginBottom: 8 }}>{total} result{total === 1 ? "" : "s"}</p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
        {items.length === 0 && <div className="muted">No matches. Try clearing filters or another keyword.</div>}
        {items.map((c) => (
          <div className="tile browse-tile" key={c.id}>
            <div className="tile-art">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                className="tile-poster"
                src={coursePosterUrl({
                  title: c.title,
                  category: c.category,
                  subject: c.subject,
                  tags: c.tags,
                  format: c.format,
                  thumbnail: c.thumbnail,
                })}
                alt=""
                loading="lazy"
              />
              <div className="tile-art-scrim" aria-hidden />
            </div>
            <div className="tile-body">
            <h3 style={{ marginBottom: 4, fontSize: 14 }}>{c.title}</h3>
            <div className="muted" style={{ fontSize: 12 }}>
              {FORMAT_LABELS[c.format] || c.format} · {c.category || c.subject} · {c.level}
              {c.duration_min ? ` · ${c.duration_min} min` : ""}
            </div>
            <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap" }}>
              <span className="pill" style={{ color: "#0ea5e9" }}>{SOURCE_LABELS[c.source] || c.source}</span>
              {c.drive_safe && <span className="pill" style={{ color: "#16a34a" }}>drive-safe</span>}
            </div>
            <p className="muted" style={{ marginTop: 6 }}>{c.preview || c.subtitle}</p>
            <div className="row" style={{ marginTop: 8, gap: 8 }}>
              <button type="button" onClick={() => openItem(c)}>Open</button>
              {c.source === "catalog" && (
                <button type="button" onClick={() => onEnroll(c)}>Enroll</button>
              )}
            </div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

function Facet({ label, value, onChange, options, optionValues, formatLabels }: {
  label: string; value: string; onChange: (v: string) => void; options?: string[];
  optionValues?: string[]; formatLabels?: Record<string, string>;
}) {
  const values = optionValues ?? options ?? [];
  const labels = options ?? values;
  return (
    <label style={{ fontSize: 13 }}>
      {label}&nbsp;
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Any</option>
        {values.map((v, i) => (
          <option key={v} value={v}>
            {formatLabels?.[v] || labels[i] || v}
          </option>
        ))}
      </select>
    </label>
  );
}

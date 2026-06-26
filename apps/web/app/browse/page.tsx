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
import { CoursePosterImg } from "../components/CoursePosterImg";
import { useT } from "../lib/i18n";

export default function BrowsePage() {
  const router = useRouter();
  const { t, locale } = useT();
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

  const formatLabel = (f: string) => t(`browse.format.${f}`) !== `browse.format.${f}` ? t(`browse.format.${f}`) : f;
  const sourceLabel = (s: string) => t(`browse.source.${s}`) !== `browse.source.${s}` ? t(`browse.source.${s}`) : s;

  useEffect(() => {
    const authed = Boolean(getToken());
    setLoggedIn(authed);
    setAuthResolved(true);
    if (!authed) return;
    getLearnFacets().then(setFacets).catch(() => setFacets(null));
  }, []);

  useEffect(() => {
    if (!loggedIn) return;
    searchLearnable({ ...filters, limit: "80" }, locale)
      .then((r) => { setItems(r.items); setTotal(r.total); })
      .catch((e) => setError(String(e)));
  }, [filters, loggedIn, locale]);

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
      setMsg(t("browse.signInEnroll"));
      return;
    }
    if (item.source !== "catalog") {
      openItem(item);
      return;
    }
    try {
      await enrollCourse(item.source_id, item.title);
      setMsg(t("browse.enrolled", { title: item.title }));
    } catch (e) {
      setError(String(e));
    }
  }

  if (!authResolved) {
    return (
      <main className="container">
        <p className="muted">{t("browse.loading")}</p>
      </main>
    );
  }

  if (!loggedIn) {
    return (
      <main className="container">
        <h1>{t("browse.title")}</h1>
        <div className="card">
          <p>{t("browse.signIn")} <Link href="/login">{t("profile.signIn")}</Link></p>
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <h1>{t("browse.heading")}</h1>
      <p className="muted">{t("browse.subtitle")}</p>

      <div className="card">
        <input
          placeholder={t("browse.searchPlaceholder")}
          value={filters.q}
          onChange={(e) => set("q", e.target.value)}
          style={{ width: "100%", padding: 8, marginBottom: 8 }}
        />
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          <Facet label={t("browse.category")} value={filters.category} onChange={(v) => set("category", v)} options={facets?.categories} />
          <Facet label={t("browse.type")} value={filters.format} onChange={(v) => set("format", v)}
            options={facets?.formats?.map((f) => formatLabel(f))}
            optionValues={facets?.formats} />
          <Facet label={t("browse.source")} value={filters.source} onChange={(v) => set("source", v)}
            options={facets?.sources?.map((s) => sourceLabel(s))}
            optionValues={facets?.sources} />
          <Facet label={t("browse.language")} value={filters.language} onChange={(v) => set("language", v)} options={facets?.languages} />
          <Facet label={t("browse.level")} value={filters.level} onChange={(v) => set("level", v)} options={facets?.levels} />
          <label style={{ fontSize: 13 }}>
            {t("browse.for")}&nbsp;
            <select value={filters.audience} onChange={(e) => set("audience", e.target.value)}>
              <option value="">{t("browse.anyone")}</option>
              {(facets?.audiences ?? []).map((a) => (
                <option key={a.slug} value={a.slug}>{a.label}</option>
              ))}
            </select>
          </label>
          <label className="row">
            <input type="checkbox" checked={filters.hands_on === "true"}
              onChange={(e) => set("hands_on", e.target.checked ? "true" : "")} />
            &nbsp;{t("browse.handsOn")}
          </label>
        </div>
      </div>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}
      {msg && <div className="card" style={{ borderColor: "#34d399" }}><div className="muted">{msg}</div></div>}

      <p className="muted" style={{ marginBottom: 8 }}>
        {total === 1 ? t("browse.resultOne") : t("browse.results", { total })}
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
        {items.length === 0 && <div className="muted">{t("browse.noMatches")}</div>}
        {items.map((c) => (
          <div className="tile browse-tile" key={c.id}>
            <div className="tile-art">
              <CoursePosterImg
                className="tile-poster"
                input={{
                  title: c.title,
                  category: c.category,
                  subject: c.subject,
                  tags: c.tags,
                  format: c.format,
                  thumbnail: c.thumbnail,
                }}
              />
              <div className="tile-art-scrim" aria-hidden />
            </div>
            <div className="tile-body">
            <h3 style={{ marginBottom: 4, fontSize: 14 }}>{c.title}</h3>
            <div className="muted" style={{ fontSize: 12 }}>
              {formatLabel(c.format)} · {c.category || c.subject} · {c.level}
              {c.duration_min ? ` · ${c.duration_min} min` : ""}
            </div>
            <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap" }}>
              <span className="pill" style={{ color: "#0ea5e9" }}>{sourceLabel(c.source)}</span>
              {c.drive_safe && <span className="pill" style={{ color: "#16a34a" }}>{t("browse.driveSafe")}</span>}
            </div>
            <p className="muted" style={{ marginTop: 6 }}>{c.preview || c.subtitle}</p>
            <div className="row" style={{ marginTop: 8, gap: 8 }}>
              <button type="button" onClick={() => openItem(c)}>{t("browse.open")}</button>
              {c.source === "catalog" && (
                <button type="button" onClick={() => onEnroll(c)}>{t("browse.enroll")}</button>
              )}
            </div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

function Facet({ label, value, onChange, options, optionValues }: {
  label: string; value: string; onChange: (v: string) => void; options?: string[];
  optionValues?: string[];
}) {
  const { t } = useT();
  const values = optionValues ?? options ?? [];
  const labels = options ?? values;
  return (
    <label style={{ fontSize: 13 }}>
      {label}&nbsp;
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t("browse.any")}</option>
        {values.map((v, i) => (
          <option key={v} value={v}>
            {labels[i] || v}
          </option>
        ))}
      </select>
    </label>
  );
}

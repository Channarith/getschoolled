"use client";

import { useMemo, useState } from "react";
import { cleanTitle, type Progress } from "../lib/onTheGoCatalog";

type Row = { id: string; title: string; category?: string; duration_min?: number; level?: string; segments?: number };

type Props = {
  rows: Row[];
  selectedId: string;
  loading: boolean;
  progress: Progress;
  labels: { search: string; choose: string; none: string; loading: string; resume: string; all: string };
  onSelect: (id: string) => void;
};

/** Quiet course list: search box, category chips, one row per course with length and a resume mark. */
export default function OnTheGoCoursePicker({ rows, selectedId, loading, progress, labels, onSelect }: Props) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const cats = useMemo(() => Array.from(new Set(rows.map((r) => r.category || "").filter(Boolean))).sort(), [rows]);
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) =>
      (!cat || r.category === cat) &&
      (!needle || `${r.title} ${r.category || ""}`.toLowerCase().includes(needle)));
  }, [rows, q, cat]);

  return (
    <div data-testid="on-the-go-picker" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <input
        type="search" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder={labels.search} aria-label={labels.search}
        style={{ minHeight: 44, borderRadius: 12, border: "1.5px solid rgba(212,175,55,.7)", background: "#101820", color: "#f4fbff", fontSize: 16, padding: "0 12px" }}
      />
      {cats.length > 1 && (
        <div role="group" aria-label="Categories" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {["", ...cats].map((c) => (
            <button
              key={c || "all"} type="button" aria-pressed={cat === c} onClick={() => setCat(c)}
              style={{
                padding: "4px 10px", borderRadius: 999, fontSize: 12, cursor: "pointer",
                border: "1.5px solid rgba(212,175,55,.7)",
                background: cat === c ? "#d4af37" : "transparent", color: cat === c ? "#0b1020" : "#e8ecf6", fontWeight: cat === c ? 700 : 500,
              }}
            >{c || labels.all}</button>
          ))}
        </div>
      )}
      <ul role="listbox" aria-label={labels.choose} style={{ listStyle: "none", margin: 0, padding: 0, maxHeight: 260, overflowY: "auto", display: "grid", gap: 6 }}>
        {shown.map((r) => {
          const selected = r.id === selectedId;
          const saved = progress.courses[r.id];
          return (
            <li key={r.id} role="option" aria-selected={selected}>
              <button
                type="button" data-testid={`otg-course-${r.id}`} onClick={() => onSelect(r.id)}
                style={{
                  width: "100%", textAlign: "left", cursor: "pointer", padding: "10px 12px", borderRadius: 12,
                  border: `1.5px solid ${selected ? "#d4af37" : "rgba(212,175,55,.3)"}`,
                  background: selected ? "rgba(212,175,55,.14)" : "#101820", color: "#f4fbff",
                  display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center",
                }}
              >
                <span style={{ display: "grid", gap: 2 }}>
                  <span style={{ fontSize: 16, fontWeight: 650 }}>{cleanTitle(r.title)}</span>
                  <span style={{ fontSize: 12, color: "#9fbac2" }}>
                    {[r.category, r.duration_min ? `${r.duration_min} min` : "", r.level].filter(Boolean).join(" · ")}
                  </span>
                </span>
                {saved && saved.seg > 0 && (
                  <span style={{ fontSize: 11, color: "#fde047", whiteSpace: "nowrap" }}>{labels.resume} {saved.seg + 1}</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      {loading && <p className="muted" style={{ margin: 0 }}>{labels.loading}</p>}
      {!loading && shown.length === 0 && <p className="muted" style={{ margin: 0 }}>{labels.none}</p>}
    </div>
  );
}

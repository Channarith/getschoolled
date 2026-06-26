"use client";

import { useEffect, useState } from "react";
import {
  BACKGROUNDS,
  CATEGORIES,
  backgroundLayerStyle,
  backgroundMotionClass,
  getBackground,
  seasonalBackgroundId,
  type Background,
} from "../lib/backgrounds";
import { BG_AUTO_KEY, BG_EVENT, BG_KEY } from "../components/BackgroundProvider";

const CATEGORY_LABELS: Record<string, string> = {
  holiday: "Holiday", seasonal: "Seasonal", social: "Social", economic: "Economic",
  realistic: "Realistic", surreal: "Surreal", artistic: "Artistic", kids: "Kids",
  anime: "Anime", minimal: "Minimal",
};

export default function BackgroundsPage() {
  const [auto, setAuto] = useState(true);
  const [selected, setSelected] = useState<string>("");
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    const a = window.localStorage.getItem(BG_AUTO_KEY);
    setAuto(a === null || a === "1");
    setSelected(window.localStorage.getItem(BG_KEY) || seasonalBackgroundId());
  }, []);

  function apply(id: string) {
    window.localStorage.setItem(BG_KEY, id);
    window.localStorage.setItem(BG_AUTO_KEY, "0");
    setSelected(id);
    setAuto(false);
    window.dispatchEvent(new Event(BG_EVENT));
  }

  function setAutoMode(on: boolean) {
    window.localStorage.setItem(BG_AUTO_KEY, on ? "1" : "0");
    setAuto(on);
    if (on) setSelected(seasonalBackgroundId());
    window.dispatchEvent(new Event(BG_EVENT));
  }

  const shown: Background[] =
    filter === "all" ? BACKGROUNDS : BACKGROUNDS.filter((b) => b.category === filter);
  const todays = getBackground(seasonalBackgroundId());

  return (
    <main className="container" style={{ maxWidth: 1100 }}>
      <h1>Backgrounds &amp; wallpapers</h1>
      <p className="muted">
        {BACKGROUNDS.length}+ designs across holidays, seasons, social, economic,
        realistic, surreal, artistic, kids and anime styles. Pick one, or use
        <strong> Auto</strong> to rotate by date all year.
      </p>

      <div className="card" style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={auto} onChange={(e) => setAutoMode(e.target.checked)} />
          <strong>Auto</strong> (seasonal / holiday)
        </label>
        <span className="muted">
          Today&rsquo;s pick: <strong>{todays.name}</strong> ({CATEGORY_LABELS[todays.category]})
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button onClick={() => setFilter("all")}
            style={{ fontSize: 12, opacity: filter === "all" ? 1 : 0.6 }}>All</button>
          {CATEGORIES.map((c) => (
            <button key={c} onClick={() => setFilter(c)}
              style={{ fontSize: 12, opacity: filter === c ? 1 : 0.6 }}>
              {CATEGORY_LABELS[c]}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 14, marginTop: 8 }}>
        {shown.map((b) => {
          const active = !auto && selected === b.id;
          return (
            <button key={b.id} onClick={() => apply(b.id)} title={`Apply ${b.name}`}
              style={{
                padding: 0, border: active ? "3px solid #6ea8fe" : "1px solid var(--border)",
                borderRadius: 12, overflow: "hidden", cursor: "pointer", background: "none", textAlign: "left",
              }}>
              <div className="site-bg-preview" style={{ height: 120 }}>
                <div
                  className={`site-bg-preview-layer ${backgroundMotionClass(b)}`}
                  style={backgroundLayerStyle(b)}
                />
              </div>
              <div style={{ padding: "8px 10px", background: "var(--panel)" }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text)" }}>{b.name}</div>
                <div className="muted" style={{ fontSize: 11 }}>
                  {CATEGORY_LABELS[b.category]}{b.kind === "image" ? " · image" : ""}{active ? " · active" : ""}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </main>
  );
}

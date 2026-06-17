"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  DEFAULT_THEME_ID,
  getTheme,
  themeList,
  type Theme,
} from "./lib/themes";

function themeVars(theme: Theme): React.CSSProperties {
  const p = theme.palette;
  return {
    // Exposed as CSS variables consumed by the themed classes below.
    ["--t-bg" as string]: p.bg,
    ["--t-panel" as string]: p.panel,
    ["--t-accent" as string]: p.accent,
    ["--t-accent2" as string]: p.accent2,
    ["--t-text" as string]: p.text,
    ["--t-muted" as string]: p.muted,
    ["--t-border" as string]: p.border,
    ["--t-radius" as string]: theme.radius,
    fontFamily: theme.font,
  };
}

export default function HomePage() {
  const [themeId, setThemeId] = useState<string>(DEFAULT_THEME_ID);

  // Resolve the active theme from ?theme= or the saved preference on mount.
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("theme");
    const saved = window.localStorage.getItem("aoep-theme");
    const initial = fromUrl || saved || DEFAULT_THEME_ID;
    setThemeId(initial);
  }, []);

  function selectTheme(id: string) {
    setThemeId(id);
    window.localStorage.setItem("aoep-theme", id);
    const url = new URL(window.location.href);
    url.searchParams.set("theme", id);
    window.history.replaceState({}, "", url.toString());
  }

  const theme = useMemo(() => getTheme(themeId), [themeId]);
  const bgImage = theme.background
    ? `${theme.overlay}, url(${theme.background})`
    : theme.overlay;

  return (
    <div className="themed" style={themeVars(theme)}>
      <section
        className="theme-hero"
        style={{ backgroundImage: bgImage }}
        data-gamified={theme.gamified ? "1" : "0"}
      >
        <div className="theme-hero-inner">
          <div className="theme-toolbar">
            <span className="theme-badge">
              {theme.decoration} {theme.hero.badge}
            </span>
            <label className="theme-picker">
              <span className="muted">Template</span>
              <select
                value={theme.id}
                onChange={(e) => selectTheme(e.target.value)}
                aria-label="Choose a landing template"
              >
                {themeList().map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} — {t.audience}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <h1 className="theme-title">{theme.hero.title}</h1>
          <p className="theme-subtitle">{theme.hero.subtitle}</p>

          {theme.gamified && (
            <div className="gami-row" aria-hidden="true">
              <span className="gami-badge">🏅 Level 1</span>
              <span className="gami-badge">🔥 3-day streak</span>
              <span className="gami-badge">⭐ 120 XP</span>
            </div>
          )}
        </div>
      </section>

      <section className="theme-cards">
        {theme.cards.map((card) => (
          <div className="theme-card" key={card.title}>
            <h3>{card.title}</h3>
            <p className="muted">{card.body}</p>
            <Link href={card.href}>
              <button className="theme-btn">{card.cta}</button>
            </Link>
          </div>
        ))}
      </section>

      <p className="theme-foot muted">
        Showing the <strong>{theme.name}</strong> template ·{" "}
        {themeList().length} audience templates available · switch any time.
      </p>
    </div>
  );
}

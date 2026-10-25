"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cleanTitle, type Progress } from "../lib/onTheGoCatalog";
import { badgeFor, rankCourses, windowRows, type SearchRow } from "../lib/onTheGoSearch";

const ROW_H = 64;
const LIST_H = 288;

type Props = {
  rows: SearchRow[];
  /** Language family of the picked voice ("en", "es", "yue"). */
  language: string;
  /** Names for badges: { es: "Español", ... }. */
  languageNames: Record<string, string>;
  query: string;
  onQuery: (q: string) => void;
  includeEnglish: boolean;
  onIncludeEnglish: (v: boolean) => void;
  /** Anonymous demo: only these courses are searchable. */
  allowedIds?: readonly string[];
  selectedId: string;
  loading: boolean;
  progress: Progress;
  labels: {
    placeholder: string; includeEnglish: string; readyIn: (lang: string) => string; otherLangs: (langs: string) => string;
    englishOnly: string; emptyLang: (lang: string) => string; noMatch: (q: string) => string; count: (n: number) => string;
    voiceHint: string; loading: string; resume: string; choose: string;
  };
  onSelect: (id: string) => void;
};

/** Always-visible course search: fuzzy, ready-in-your-language first, with a windowed list so the full catalog stays fast. */
export default function OnTheGoCourseSearch({
  rows, language, languageNames, query, onQuery, includeEnglish, onIncludeEnglish, allowedIds, selectedId, loading, progress, labels, onSelect,
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [active, setActive] = useState(-1);

  // Desktop: the search box is ready to type in. Touch devices keep the keyboard closed until the box is tapped.
  useEffect(() => {
    try {
      if (window.matchMedia("(pointer: fine)").matches) inputRef.current?.focus({ preventScroll: true });
    } catch { /* no matchMedia */ }
  }, []);

  const shown = useMemo(
    () => rankCourses(rows, query, { language, includeEnglish, allowedIds }),
    [rows, query, language, includeEnglish, allowedIds],
  );
  const pool = useMemo(() => (allowedIds ? rows.filter((r) => allowedIds.includes(r.id)) : rows), [rows, allowedIds]);
  const readyCount = useMemo(() => pool.filter((r) => language === "en" || r.ready).length, [pool, language]);
  const langName = languageNames[language] || language;
  const noneReady = language !== "en" && !loading && pool.length > 0 && readyCount === 0;

  useEffect(() => { setScrollTop(0); setActive(-1); if (listRef.current) listRef.current.scrollTop = 0; }, [query, language, includeEnglish]);

  const win = windowRows(shown.length, scrollTop, LIST_H, ROW_H);
  const visible = shown.slice(win.start, win.end);

  function reveal(index: number) {
    const el = listRef.current;
    if (!el) return;
    const top = index * ROW_H;
    if (top < el.scrollTop) el.scrollTop = top;
    else if (top + ROW_H > el.scrollTop + LIST_H) el.scrollTop = top + ROW_H - LIST_H;
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!shown.length) return;
      const next = e.key === "ArrowDown" ? Math.min(shown.length - 1, active + 1) : Math.max(0, active - 1);
      setActive(next);
      reveal(next);
    } else if (e.key === "Enter") {
      const pick = shown[active >= 0 ? active : 0];
      if (pick) { e.preventDefault(); onSelect(pick.id); }
    } else if (e.key === "Escape" && query) {
      onQuery("");
    }
  }

  return (
    <div data-testid="on-the-go-search" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <input
        ref={inputRef} type="search" value={query} data-testid="otg-search-input"
        onChange={(e) => onQuery(e.target.value)} onKeyDown={onKeyDown}
        placeholder={labels.placeholder} aria-label={labels.placeholder}
        role="combobox" aria-expanded="true" aria-controls="otg-search-list" aria-autocomplete="list"
        aria-activedescendant={active >= 0 && shown[active] ? `otg-opt-${shown[active].id}` : undefined}
        enterKeyHint="search" autoComplete="off" spellCheck={false} dir="auto"
        style={{ minHeight: 48, borderRadius: 12, border: "1.5px solid rgba(212,175,55,.8)", background: "#101820", color: "#f4fbff", fontSize: 16, padding: "0 14px" }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap", fontSize: 12, color: "#9fbac2" }}>
        <span>{labels.voiceHint}</span>
        {language !== "en" && (
          <label style={{ display: "inline-flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
            <input
              type="checkbox" data-testid="otg-include-english" checked={includeEnglish}
              onChange={(e) => onIncludeEnglish(e.target.checked)}
            />
            {labels.includeEnglish}
          </label>
        )}
      </div>
      <div role="status" aria-live="polite" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
        {loading ? labels.loading : labels.count(shown.length)}
      </div>
      {noneReady && (
        <p data-testid="otg-empty-language" className="muted" style={{ margin: 0, fontSize: 13 }}>{labels.emptyLang(langName)}</p>
      )}
      <div
        ref={listRef} id="otg-search-list" role="listbox" aria-label={labels.choose} data-testid="otg-search-list"
        onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
        style={{ height: Math.min(LIST_H, Math.max(ROW_H, shown.length * ROW_H)), overflowY: "auto", position: "relative" }}
      >
        <div style={{ paddingTop: win.padTop, paddingBottom: win.padBottom }}>
          {visible.map((r, k) => {
            const index = win.start + k;
            const selected = r.id === selectedId;
            const saved = progress.courses[r.id];
            const badge = badgeFor(r, language);
            const text = r.title_local || r.title;
            return (
              <div key={r.id} id={`otg-opt-${r.id}`} role="option" aria-selected={selected} style={{ height: ROW_H, boxSizing: "border-box", padding: "3px 0" }}>
                <button
                  type="button" data-testid={`otg-course-${r.id}`} data-active={index === active ? "1" : undefined} onClick={() => onSelect(r.id)}
                  style={{
                    width: "100%", height: "100%", textAlign: "start", cursor: "pointer", padding: "6px 12px", borderRadius: 12,
                    border: `1.5px solid ${selected || index === active ? "#d4af37" : "rgba(212,175,55,.3)"}`,
                    background: selected ? "rgba(212,175,55,.14)" : "#101820", color: "#f4fbff",
                    display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center",
                  }}
                >
                  <span style={{ display: "grid", gap: 2, minWidth: 0 }}>
                    <span dir="auto" style={{ fontSize: 16, fontWeight: 650, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cleanTitle(text)}</span>
                    <span style={{ fontSize: 12, color: "#9fbac2", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {[r.category, r.duration_min ? `${r.duration_min} min` : "", r.level].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                  <span style={{ display: "grid", gap: 3, justifyItems: "end", flexShrink: 0 }}>
                    {language !== "en" && (
                      <span
                        data-testid={`otg-badge-${r.id}`} data-kind={badge.kind}
                        style={{
                          fontSize: 11, padding: "1px 8px", borderRadius: 999, whiteSpace: "nowrap",
                          background: badge.kind === "ready" ? "rgba(34,197,94,.18)" : "rgba(148,163,184,.15)",
                          color: badge.kind === "ready" ? "#86efac" : "#cbd5e1",
                          border: `1px solid ${badge.kind === "ready" ? "rgba(34,197,94,.5)" : "rgba(148,163,184,.35)"}`,
                        }}
                      >
                        {badge.kind === "ready" ? labels.readyIn(langName)
                          : badge.kind === "other" ? labels.otherLangs(badge.languages.map((l) => languageNames[l] || l).join(", "))
                          : labels.englishOnly}
                      </span>
                    )}
                    {saved && saved.seg > 0 && (
                      <span style={{ fontSize: 11, color: "#fde047", whiteSpace: "nowrap" }}>{labels.resume} {saved.seg + 1}</span>
                    )}
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      </div>
      {!loading && shown.length === 0 && (
        <p data-testid="otg-no-match" className="muted" style={{ margin: 0 }}>{labels.noMatch(query.trim())}</p>
      )}
    </div>
  );
}

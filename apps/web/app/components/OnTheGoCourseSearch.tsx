"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cleanTitle, type Progress } from "../lib/onTheGoCatalog";
import { badgeFor, rankCourses, windowRows, type SearchRow } from "../lib/onTheGoSearch";

const ROW_H = 56;
/** About six rows: the last one is cut off on purpose so it is clear the list scrolls. */
const LIST_H = 308;

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

/**
 * One closed dropdown showing the current course. Opening it shows a short scrollable list with a type-to-filter box on top.
 * Ranking and the "Ready in <language>" badge come from the pre-translated search; the list is windowed so the full catalog stays fast.
 */
export default function OnTheGoCourseSearch({
  rows, language, languageNames, query, onQuery, includeEnglish, onIncludeEnglish, allowedIds, selectedId, loading, progress, labels, onSelect,
}: Props) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [scrollTop, setScrollTop] = useState(0);
  const [active, setActive] = useState(-1);

  const shown = useMemo(
    () => rankCourses(rows, query, { language, includeEnglish, allowedIds }),
    [rows, query, language, includeEnglish, allowedIds],
  );
  const pool = useMemo(() => (allowedIds ? rows.filter((r) => allowedIds.includes(r.id)) : rows), [rows, allowedIds]);
  const readyCount = useMemo(() => pool.filter((r) => language === "en" || r.ready).length, [pool, language]);
  const langName = languageNames[language] || language;
  const noneReady = language !== "en" && !loading && pool.length > 0 && readyCount === 0;
  const current = useMemo(() => rows.find((r) => r.id === selectedId), [rows, selectedId]);
  const currentTitle = current ? cleanTitle(current.title_local || current.title) : "";

  useEffect(() => { setScrollTop(0); setActive(-1); if (listRef.current) listRef.current.scrollTop = 0; }, [query, language, includeEnglish, open]);

  // A spoken "search for ..." sets the query from outside: show the results.
  useEffect(() => { if (query) setOpen(true); }, [query]);

  // Desktop: typing works as soon as the list opens. Touch keeps the keyboard closed until the box is tapped.
  useEffect(() => {
    if (!open) return;
    try {
      if (window.matchMedia("(pointer: fine)").matches) inputRef.current?.focus({ preventScroll: true });
    } catch { /* no matchMedia */ }
  }, [open]);

  // Click or tap outside closes the list.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  const win = windowRows(shown.length, scrollTop, LIST_H, ROW_H);
  const visible = shown.slice(win.start, win.end);

  function reveal(index: number) {
    const el = listRef.current;
    if (!el) return;
    const top = index * ROW_H;
    if (top < el.scrollTop) el.scrollTop = top;
    else if (top + ROW_H > el.scrollTop + LIST_H) el.scrollTop = top + ROW_H - LIST_H;
  }

  function close(focusTrigger = true) {
    setOpen(false);
    if (focusTrigger) triggerRef.current?.focus();
  }

  function choose(id: string) {
    onSelect(id);
    close();
  }

  function onTriggerKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setOpen(true); }
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
      if (pick) { e.preventDefault(); choose(pick.id); }
    } else if (e.key === "Escape") {
      e.preventDefault();
      if (query) onQuery("");
      else close();
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div ref={rootRef} data-testid="on-the-go-search" data-open={open ? "1" : "0"} style={{ position: "relative" }}>
      <button
        ref={triggerRef} type="button" data-testid="otg-trigger"
        role="combobox" aria-haspopup="listbox" aria-expanded={open} aria-controls="otg-search-popup" aria-label={labels.choose}
        onClick={() => setOpen((v) => !v)} onKeyDown={onTriggerKeyDown}
        style={{
          width: "100%", minHeight: 48, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, cursor: "pointer",
          padding: "0 14px", borderRadius: 12, border: "1.5px solid rgba(212,175,55,.8)", background: "#101820", color: "#f4fbff", fontSize: 16, textAlign: "start",
        }}
      >
        <span dir="auto" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 650 }}>
          {currentTitle || (loading ? labels.loading : labels.choose)}
        </span>
        <span aria-hidden style={{ color: "#d4af37", flexShrink: 0, transform: open ? "rotate(180deg)" : "none", transition: "transform .15s" }}>▾</span>
      </button>

      {open && (
        <div
          id="otg-search-popup" data-testid="otg-search-popup"
          style={{
            position: "absolute", left: 0, right: 0, top: "calc(100% + 6px)", zIndex: 30, display: "flex", flexDirection: "column", gap: 8,
            padding: 10, borderRadius: 14, background: "#0b1020", border: "1.5px solid rgba(212,175,55,.85)", boxShadow: "0 14px 34px rgba(0,0,0,.5)",
          }}
        >
          <input
            ref={inputRef} type="search" value={query} data-testid="otg-search-input"
            onChange={(e) => onQuery(e.target.value)} onKeyDown={onKeyDown}
            placeholder={labels.placeholder} aria-label={labels.placeholder}
            aria-controls="otg-search-list" aria-autocomplete="list"
            aria-activedescendant={active >= 0 && shown[active] ? `otg-opt-${shown[active].id}` : undefined}
            enterKeyHint="search" autoComplete="off" spellCheck={false} dir="auto"
            style={{ minHeight: 42, borderRadius: 10, border: "1.5px solid rgba(212,175,55,.6)", background: "#101820", color: "#f4fbff", fontSize: 16, padding: "0 12px" }}
          />
          {language !== "en" && (
            <label style={{ display: "inline-flex", gap: 6, alignItems: "center", cursor: "pointer", fontSize: 12, color: "#9fbac2" }}>
              <input
                type="checkbox" data-testid="otg-include-english" checked={includeEnglish}
                onChange={(e) => onIncludeEnglish(e.target.checked)}
              />
              {labels.includeEnglish}
            </label>
          )}
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
                      type="button" data-testid={`otg-course-${r.id}`} data-active={index === active ? "1" : undefined} onClick={() => choose(r.id)}
                      style={{
                        width: "100%", height: "100%", textAlign: "start", cursor: "pointer", padding: "4px 10px", borderRadius: 10,
                        border: `1.5px solid ${selected || index === active ? "#d4af37" : "rgba(212,175,55,.25)"}`,
                        background: selected ? "rgba(212,175,55,.14)" : "#101820", color: "#f4fbff",
                        display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center",
                      }}
                    >
                      <span style={{ display: "grid", gap: 1, minWidth: 0 }}>
                        <span dir="auto" style={{ fontSize: 15, fontWeight: 650, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cleanTitle(text)}</span>
                        <span style={{ fontSize: 11, color: "#9fbac2", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {[r.category, r.duration_min ? `${r.duration_min} min` : ""].filter(Boolean).join(" · ")}
                        </span>
                      </span>
                      <span style={{ display: "grid", gap: 2, justifyItems: "end", flexShrink: 0 }}>
                        {language !== "en" && (
                          <span
                            data-testid={`otg-badge-${r.id}`} data-kind={badge.kind}
                            style={{
                              fontSize: 10, padding: "1px 7px", borderRadius: 999, whiteSpace: "nowrap",
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
                          <span style={{ fontSize: 10, color: "#fde047", whiteSpace: "nowrap" }}>{labels.resume} {saved.seg + 1}</span>
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
          <span style={{ fontSize: 11, color: "#9fbac2" }}>{labels.voiceHint}</span>
        </div>
      )}
    </div>
  );
}

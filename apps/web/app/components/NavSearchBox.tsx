"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { searchLearnable, getGamesCatalog, type LearnableItem } from "../lib/api";
import { useT } from "../lib/i18n";

// Static settings pages that are searchable. Admin, flags, and password-required
// pages are intentionally excluded.
// Link only to real routes — /account has no ?tab= routing (see account/page.tsx).
const SETTINGS_ITEMS = [
  { titleKey: "search.account", href: "/account", keywords: "account settings profile email password name membership" },
  { titleKey: "search.language", href: "/languages", keywords: "language practice locale translate learn" },
  { titleKey: "search.voice", href: "/drive", keywords: "voice narration tts audio instructor speed" },
  { titleKey: "search.billing", href: "/billing", keywords: "billing plans plan tier upgrade subscription" },
  { titleKey: "search.rewards", href: "/rewards", keywords: "rewards points redeem prizes" },
  { titleKey: "search.download", href: "/download", keywords: "download app mobile ios android" },
] as const;

type GameResult = { id: string; name: string; href: string };
type SettingResult = { titleKey: (typeof SETTINGS_ITEMS)[number]["titleKey"]; href: string };

type SearchResults = {
  courses: LearnableItem[];
  games: GameResult[];
  settings: SettingResult[];
};

const EMPTY: SearchResults = { courses: [], games: [], settings: [] };

export default function NavSearchBox() {
  const { t, locale } = useT();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults>(EMPTY);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchAbortRef = useRef<AbortController | null>(null);
  const [gameSubjects, setGameSubjects] = useState<GameResult[]>([]);

  // Clear debounce timer on unmount
  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current); }, []);

  // Pre-load arcade subjects once for client-side game search
  useEffect(() => {
    getGamesCatalog()
      .then((cat) => {
        const items = (cat.subjects_localized ?? cat.subjects.map((id) => ({ id, name: id }))).map(
          (s) => ({
            id: typeof s === "string" ? s : s.id,
            name: typeof s === "string" ? s : s.name,
            href: `/arcade?subject=${encodeURIComponent(typeof s === "string" ? s : s.id)}`,
          }),
        );
        setGameSubjects(items);
      })
      .catch(() => {});
  }, []);

  // Collapse when route changes
  useEffect(() => {
    setOpen(false);
    setQuery("");
    setResults(EMPTY);
  }, [pathname]);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
        setResults(EMPTY);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        setQuery("");
        setResults(EMPTY);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const doSearch = useCallback(
    async (q: string) => {
      if (!q.trim()) {
        setResults(EMPTY);
        setLoading(false);
        return;
      }

      // Cancel any in-flight request before starting a new one
      searchAbortRef.current?.abort();
      const controller = new AbortController();
      searchAbortRef.current = controller;

      setLoading(true);
      try {
        const lower = q.toLowerCase();

        // Settings: client-side filter
        const settings = SETTINGS_ITEMS.filter(
          (s) =>
            t(s.titleKey).toLowerCase().includes(lower) ||
            s.keywords.toLowerCase().includes(lower),
        );

        // Games: client-side filter on pre-loaded subjects
        const games = gameSubjects.filter(
          (g) =>
            g.name.toLowerCase().includes(lower) ||
            g.id.toLowerCase().includes(lower),
        );

        // Courses/lessons: API call
        const courseRes = await searchLearnable({ q, limit: "6" }, locale, controller.signal);
        const courses = courseRes.items.slice(0, 6);

        setResults({ courses, games: games.slice(0, 4), settings: settings.slice(0, 3) });
      } catch (err) {
        // Ignore aborted requests; silently fail others — search is a progressive enhancement
        if (err instanceof Error && err.name === "AbortError") return;
        setResults(EMPTY);
      } finally {
        setLoading(false);
      }
    },
    [gameSubjects, locale, t],
  );

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value;
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void doSearch(q), 300);
  };

  const openSearch = () => {
    setOpen(true);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const navigate = (href: string) => {
    setOpen(false);
    setQuery("");
    setResults(EMPTY);
    router.push(href);
  };

  const hasResults =
    results.courses.length > 0 || results.games.length > 0 || results.settings.length > 0;
  const showDropdown = open && query.trim().length > 0;

  return (
    <div ref={containerRef} className="nav-search-wrap" role="search" aria-label={t("nav.siteSearch")}>
      {!open ? (
        <button
          type="button"
          className="nav-search-btn"
          aria-label={t("nav.openSearch")}
          onClick={openSearch}
        >
          &#x1F50D;
        </button>
      ) : (
        <div className="nav-search-expanded">
          <input
            ref={inputRef}
            type="search"
            className="nav-search-input"
            placeholder={t("nav.searchPlaceholder")}
            value={query}
            onChange={handleInput}
            aria-label={t("nav.search")}
            autoComplete="off"
          />
          <button
            type="button"
            className="nav-search-close"
            aria-label={t("nav.closeSearch")}
            onClick={() => { setOpen(false); setQuery(""); setResults(EMPTY); }}
          >
            ✕
          </button>
        </div>
      )}

      {showDropdown && (
        <div className="nav-search-dropdown" role="listbox" aria-label={t("nav.results")}>
          {loading && <div className="nav-search-loading">{t("nav.searching")}</div>}

          {!loading && !hasResults && (
            <div className="nav-search-empty">{t("nav.noResults", { query })}</div>
          )}

          {results.courses.length > 0 && (
            <section className="nav-search-section">
              <div className="nav-search-section-label">{t("nav.courses")}</div>
              {results.courses.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="nav-search-result"
                  role="option"
                  aria-selected="false"
                  onClick={() => navigate(
                    item.deep_link ||
                    (item.format === "audio" ? `/drive?course=${encodeURIComponent(item.source_id)}` :
                     item.format === "live_class" ? `/class?lesson=${encodeURIComponent(item.source_id)}` :
                     item.format === "game" ? `/arcade?subject=${encodeURIComponent(item.source_id)}` :
                     item.format === "language" ? `/languages?code=${encodeURIComponent(item.source_id)}` :
                     `/browse?q=${encodeURIComponent(item.title)}`)
                  )}
                >
                  <span className="nav-search-result-title">{item.title}</span>
                  {item.category && (
                    <span className="nav-search-result-meta">
                      {item.format === "audio" ? `🎧 ${t("nav.audio")}` :
                       item.format === "live_class" ? `🎓 ${t("nav.liveClass")}` :
                       item.format === "game" ? `🎮 ${t("nav.game")}` :
                       item.category}
                    </span>
                  )}
                </button>
              ))}
            </section>
          )}

          {results.games.length > 0 && (
            <section className="nav-search-section">
              <div className="nav-search-section-label">{t("nav.games")}</div>
              {results.games.map((game) => (
                <button
                  key={game.id}
                  type="button"
                  className="nav-search-result"
                  role="option"
                  aria-selected="false"
                  onClick={() => navigate(game.href)}
                >
                  <span className="nav-search-result-title">{game.name}</span>
                  <span className="nav-search-result-meta">{t("nav.arcade")}</span>
                </button>
              ))}
            </section>
          )}

          {results.settings.length > 0 && (
            <section className="nav-search-section">
              <div className="nav-search-section-label">{t("nav.settings")}</div>
              {results.settings.map((s) => (
                <button
                  key={s.href}
                  type="button"
                  className="nav-search-result"
                  role="option"
                  aria-selected="false"
                  onClick={() => navigate(s.href)}
                >
                  <span className="nav-search-result-title">{t(s.titleKey)}</span>
                  <span className="nav-search-result-meta">{t("nav.settings")}</span>
                </button>
              ))}
            </section>
          )}
        </div>
      )}
    </div>
  );
}

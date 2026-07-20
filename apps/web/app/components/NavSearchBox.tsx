"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { searchLearnable, getGamesCatalog, type LearnableItem } from "../lib/api";

// Static settings pages that are searchable. Admin, flags, and password-required
// pages are intentionally excluded.
const SETTINGS_ITEMS = [
  { title: "Account settings", href: "/account", keywords: "profile email password name" },
  { title: "Language", href: "/account?tab=language", keywords: "locale language translate" },
  { title: "Voice & Audio", href: "/account?tab=voice", keywords: "voice tts audio narration speed" },
  { title: "Notifications", href: "/account?tab=notifications", keywords: "email push notification" },
  { title: "Subscription", href: "/account?tab=subscription", keywords: "plan billing tier upgrade" },
  { title: "Accessibility", href: "/account?tab=accessibility", keywords: "captions screen reader assistive" },
  { title: "Download app", href: "/download", keywords: "mobile ios android app" },
];

type GameResult = { id: string; name: string; href: string };
type SettingResult = { title: string; href: string };

type SearchResults = {
  courses: LearnableItem[];
  games: GameResult[];
  settings: SettingResult[];
};

const EMPTY: SearchResults = { courses: [], games: [], settings: [] };

export default function NavSearchBox() {
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
            s.title.toLowerCase().includes(lower) ||
            s.keywords.toLowerCase().includes(lower),
        );

        // Games: client-side filter on pre-loaded subjects
        const games = gameSubjects.filter(
          (g) =>
            g.name.toLowerCase().includes(lower) ||
            g.id.toLowerCase().includes(lower),
        );

        // Courses/lessons: API call
        const courseRes = await searchLearnable({ q, limit: "6" }, "en", controller.signal);
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
    [gameSubjects],
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
    <div ref={containerRef} className="nav-search-wrap" role="search" aria-label="Site search">
      {!open ? (
        <button
          type="button"
          className="nav-search-btn"
          aria-label="Open search"
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
            placeholder="Search courses, games, settings…"
            value={query}
            onChange={handleInput}
            aria-label="Search"
            autoComplete="off"
          />
          <button
            type="button"
            className="nav-search-close"
            aria-label="Close search"
            onClick={() => { setOpen(false); setQuery(""); setResults(EMPTY); }}
          >
            ✕
          </button>
        </div>
      )}

      {showDropdown && (
        <div className="nav-search-dropdown" role="listbox" aria-label="Search results">
          {loading && <div className="nav-search-loading">Searching…</div>}

          {!loading && !hasResults && (
            <div className="nav-search-empty">No results for &ldquo;{query}&rdquo;</div>
          )}

          {results.courses.length > 0 && (
            <section className="nav-search-section">
              <div className="nav-search-section-label">Courses</div>
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
                      {item.format === "audio" ? "🎧 Audio" :
                       item.format === "live_class" ? "🎓 Live Class" :
                       item.format === "game" ? "🎮 Game" :
                       item.category}
                    </span>
                  )}
                </button>
              ))}
            </section>
          )}

          {results.games.length > 0 && (
            <section className="nav-search-section">
              <div className="nav-search-section-label">Arcade Games</div>
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
                  <span className="nav-search-result-meta">Arcade</span>
                </button>
              ))}
            </section>
          )}

          {results.settings.length > 0 && (
            <section className="nav-search-section">
              <div className="nav-search-section-label">Settings</div>
              {results.settings.map((s) => (
                <button
                  key={s.href}
                  type="button"
                  className="nav-search-result"
                  role="option"
                  aria-selected="false"
                  onClick={() => navigate(s.href)}
                >
                  <span className="nav-search-result-title">{s.title}</span>
                  <span className="nav-search-result-meta">Settings</span>
                </button>
              ))}
            </section>
          )}
        </div>
      )}
    </div>
  );
}

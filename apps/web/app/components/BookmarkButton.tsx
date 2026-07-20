"use client";

// BookmarkButton — save/unsave a course to My List.
// Renders a ＋ / ✓ icon that toggles the "saved" enrollment status.
// Passes the auth check silently; shows nothing when logged out.
//
// Uses a module-level shared promise so N cards on one page make exactly ONE
// GET /portfolio request (deduplication), avoiding 429 rate-limit errors.

import { useEffect, useState } from "react";
import { getPortfolio, getToken, saveForLater, unsaveForLater } from "../lib/api";

// Shared in-flight portfolio fetch: all instances reuse the same promise for
// 30 seconds, then the cache is cleared so the next mount gets fresh data.
let _portfolioPromise: Promise<Set<string>> | null = null;
let _portfolioExpiry = 0;

function getSharedSavedIds(): Promise<Set<string>> {
  const now = Date.now();
  if (_portfolioPromise && now < _portfolioExpiry) return _portfolioPromise;
  _portfolioExpiry = now + 30_000; // cache for 30 s
  _portfolioPromise = getPortfolio()
    .then((p) => new Set((p.by_status?.saved ?? []).map((e: { course_id: string }) => e.course_id)))
    .catch(() => {
      // On error, clear the cache so the next mount retries rather than
      // caching an empty set for the full 30-second window.
      _portfolioPromise = null;
      _portfolioExpiry = 0;
      return new Set<string>();
    });
  return _portfolioPromise;
}

// Exported so auth/logout flows can clear stale cross-user state.
// Called automatically after save/unsave via invalidatePortfolioCache().

/** Call this after saving/unsaving so the next mount gets fresh data. */
export function invalidatePortfolioCache() {
  _portfolioPromise = null;
  _portfolioExpiry = 0;
}

type Props = {
  courseId: string;
  title: string;
  size?: number;
  style?: React.CSSProperties;
};

export default function BookmarkButton({ courseId, title, size = 22, style }: Props) {
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!getToken()) return;
    setVisible(true);
    // Use shared deduped fetch — all N cards on the page share one request.
    getSharedSavedIds()
      .then((ids) => setSaved(ids.has(courseId)))
      .catch(() => { /* silent */ });
  }, [courseId]);

  if (!visible) return null;

  async function toggle(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (busy) return;
    setBusy(true);
    try {
      if (saved) {
        await unsaveForLater(courseId);
        setSaved(false);
      } else {
        await saveForLater(courseId, title);
        setSaved(true);
      }
      invalidatePortfolioCache(); // force fresh fetch on next mount
    } catch { /* silent */ } finally {
      setBusy(false);
    }
  }

  return (
    <button
      onClick={toggle}
      title={saved ? "Remove from My List" : "Add to My List"}
      aria-label={saved ? "Remove from My List" : "Add to My List"}
      style={{
        background: saved ? "rgba(255,255,255,0.9)" : "rgba(0,0,0,0.55)",
        border: "none",
        borderRadius: "50%",
        width: size + 8,
        height: size + 8,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: busy ? "default" : "pointer",
        opacity: busy ? 0.6 : 1,
        transition: "all 0.15s",
        flexShrink: 0,
        ...style,
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill={saved ? "#0ea5e9" : "none"}
        stroke={saved ? "#0ea5e9" : "#fff"}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {saved ? (
          // Checkmark (saved)
          <polyline points="20 6 9 17 4 12" />
        ) : (
          // Plus (not saved)
          <>
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </>
        )}
      </svg>
    </button>
  );
}

"use client";

// BookmarkButton — save/unsave a course to My List.
// Renders a ＋ / ✓ icon that toggles the "saved" enrollment status.
// Passes the auth check silently; shows nothing when logged out.

import { useEffect, useState } from "react";
import { getPortfolio, getToken, saveForLater, unsaveForLater } from "../lib/api";

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
    getPortfolio()
      .then((p) => {
        const savedIds = (p.by_status?.saved ?? []).map((e) => e.course_id);
        setSaved(savedIds.includes(courseId));
      })
      .catch(() => { /* no-op if not logged in */ });
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

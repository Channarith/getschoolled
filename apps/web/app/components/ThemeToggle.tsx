"use client";

import { useEffect, useState } from "react";

/**
 * DN theme toggle (sun / moon).
 *
 * The initial `data-theme` on <html> is set by the inline bootstrap in
 * layout.tsx (reads localStorage, falls back to prefers-color-scheme). This
 * component just mirrors that state into React once mounted so the icon
 * matches, then writes the flipped value on click.
 *
 * Persistence: `localStorage["aoep.theme"] = "light" | "dark"`. Clearing it
 * returns the site to OS-level preference on the next load.
 */
export default function ThemeToggle() {
  const [mode, setMode] = useState<"light" | "dark">("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Mirror whatever the inline bootstrap chose.
    const current = document.documentElement.getAttribute("data-theme");
    setMode(current === "dark" ? "dark" : "light");
    setMounted(true);
  }, []);

  function toggle() {
    const next = mode === "dark" ? "light" : "dark";
    setMode(next);
    try {
      localStorage.setItem("aoep.theme", next);
    } catch {
      // Private mode / disabled storage — toggle still works for the session.
    }
    document.documentElement.setAttribute("data-theme", next);
    document.documentElement.style.colorScheme = next;
  }

  // Render a neutral placeholder until mounted so SSR + the inline bootstrap
  // can't disagree with React about which icon to show (prevents a flash).
  if (!mounted) {
    return (
      <button
        type="button"
        aria-label="Toggle theme"
        className="theme-toggle"
        style={{ visibility: "hidden" }}
      >
        ☾
      </button>
    );
  }

  const label = mode === "dark" ? "Switch to light mode" : "Switch to dark mode";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="theme-toggle"
    >
      {mode === "dark" ? "☀" : "☾"}
    </button>
  );
}

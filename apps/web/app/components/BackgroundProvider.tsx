"use client";

import { useEffect, useState } from "react";
import {
  DEFAULT_BACKGROUND_ID,
  backgroundStyle,
  getBackground,
  seasonalBackgroundId,
  type Background,
} from "../lib/backgrounds";

export const BG_KEY = "aoep-bg";
export const BG_AUTO_KEY = "aoep-bg-auto";
export const BG_EVENT = "aoep-bg-change";

function resolve(): Background {
  if (typeof window === "undefined") return getBackground(DEFAULT_BACKGROUND_ID);
  const auto = window.localStorage.getItem(BG_AUTO_KEY);
  // The platform default is the Salarean education wallpaper (graduation
  // caps + books + lightbulbs + pencils + Bodhi leaf on a scholarly-navy
  // gradient). Users can switch to Auto (seasonal rotation) or any
  // specific wallpaper from /backgrounds; both prefs persist in
  // localStorage. First-time visitors land on the brand default.
  if (auto === "1") return getBackground(seasonalBackgroundId());
  const explicit = window.localStorage.getItem(BG_KEY);
  return getBackground(explicit || DEFAULT_BACKGROUND_ID);
}

/** Full-bleed decorative site background applied behind all content. */
export default function BackgroundProvider() {
  const [bg, setBg] = useState<Background | null>(null);

  useEffect(() => {
    const update = () => setBg(resolve());
    update();
    window.addEventListener(BG_EVENT, update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener(BG_EVENT, update);
      window.removeEventListener("storage", update);
    };
  }, []);

  if (!bg) return null;
  return <div className="site-bg" aria-hidden style={backgroundStyle(bg)} />;
}

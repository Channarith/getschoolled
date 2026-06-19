"use client";

import { useEffect, useState } from "react";
import {
  backgroundStyle,
  getBackground,
  seasonalBackgroundId,
  type Background,
} from "../lib/backgrounds";

export const BG_KEY = "aoep-bg";
export const BG_AUTO_KEY = "aoep-bg-auto";
export const BG_EVENT = "aoep-bg-change";

function resolve(): Background {
  if (typeof window === "undefined") return getBackground(null);
  const auto = window.localStorage.getItem(BG_AUTO_KEY);
  // Default to Auto (seasonal/holiday) the first time.
  if (auto === null || auto === "1") return getBackground(seasonalBackgroundId());
  return getBackground(window.localStorage.getItem(BG_KEY));
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

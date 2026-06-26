"use client";

import { useEffect, useState } from "react";
import { resolveMascot } from "../lib/api";
import { DEFAULT_MASCOT_SRC, resolveMascotLocal } from "../lib/mascot";
import { useT } from "../lib/i18n";

type Props = {
  width?: number;
  height?: number;
  className?: string;
  style?: React.CSSProperties;
  alt?: string;
};

/** Locale-aware Bayon Buddy mascot (gated by ux.locale_mascots flag). */
export default function MascotImage({ width = 200, height, className, style, alt }: Props) {
  const { locale } = useT();
  const [src, setSrc] = useState(DEFAULT_MASCOT_SRC);
  const [title, setTitle] = useState(alt || "Salareen Bayon Buddy mascot");

  useEffect(() => {
    let cancelled = false;
    resolveMascot(locale)
      .then((res) => {
        if (cancelled) return;
        setSrc(res.path || DEFAULT_MASCOT_SRC);
        if (res.variant?.cultural_theme) {
          setTitle(`${alt || "Salareen mascot"} — ${res.variant.cultural_theme}`);
        }
      })
      .catch(() => {
        if (!cancelled) setSrc(resolveMascotLocal(locale).path);
      });
    return () => { cancelled = true; };
  }, [locale, alt]);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={title}
      title={title}
      width={width}
      height={height}
      className={className}
      style={style}
      onError={(e) => {
        const img = e.currentTarget;
        if (img.src.includes("/mascots/") && !img.src.endsWith(DEFAULT_MASCOT_SRC)) {
          img.src = DEFAULT_MASCOT_SRC;
        }
      }}
    />
  );
}

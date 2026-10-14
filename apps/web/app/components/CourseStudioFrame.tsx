"use client";

import { useEffect, useMemo, useRef } from "react";

import { useT } from "../lib/i18n";

/** Keep a same-origin studio iframe on the profile language (spoken + written). */
function withLang(src: string, locale: string): string {
  try {
    const url = new URL(src, "http://studio.local");
    url.searchParams.set("lang", locale);
    if (/^https?:\/\//i.test(src)) return url.toString();
    const query = url.searchParams.toString();
    return query ? `${url.pathname}?${query}` : url.pathname;
  } catch {
    return src;
  }
}

function applyStudioLanguage(frame: HTMLIFrameElement | null, locale: string): boolean {
  let doc: Document | null = null;
  try {
    doc = frame?.contentDocument ?? null;
  } catch {
    return false;
  }
  if (!doc) return false;
  const selects = ["teach-lang", "teach-lang-stage"]
    .map((id) => doc.getElementById(id))
    .filter((sel): sel is HTMLSelectElement => sel instanceof HTMLSelectElement);
  if (!selects.length || selects.some((sel) => sel.options.length === 0)) return false;
  const ready = selects.filter((sel) => Array.from(sel.options).some((option) => option.value === locale));
  if (!ready.length) return false;
  const needs = ready.find((sel) => sel.value !== locale);
  if (!needs) return true;
  needs.value = locale;
  needs.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

export function CourseStudioFrame({
  src,
  title,
  fill = false,
}: {
  src: string;
  title: string;
  fill?: boolean;
}) {
  const { locale } = useT();
  const frameRef = useRef<HTMLIFrameElement>(null);
  const localized = useMemo(() => withLang(src, locale), [src, locale]);

  useEffect(() => {
    let tries = 0;
    const timer = window.setInterval(() => {
      tries += 1;
      if (applyStudioLanguage(frameRef.current, locale) || tries > 24) {
        window.clearInterval(timer);
      }
    }, 400);
    return () => window.clearInterval(timer);
  }, [localized, locale]);

  return (
    <div className={fill ? "course-stage-embed" : undefined}>
      <iframe
        ref={frameRef}
        title={title}
        src={localized}
        allow="fullscreen; microphone; camera"
        style={{
          width: "100%",
          height: "100%",
          minHeight: fill ? "calc(100dvh - 9rem)" : "min(78vh, 820px)",
          border: "1px solid rgba(165,180,252,.35)",
          borderRadius: 16,
          background: "#fff",
          flex: fill ? "1 1 auto" : undefined,
        }}
      />
    </div>
  );
}

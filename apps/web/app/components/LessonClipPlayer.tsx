"use client";

import { sanitizeSvg } from "../lib/sanitizeSvg";
import { useEffect, useState } from "react";

type Props = {
  url: string;
  title?: string;
};

function svgFromDataUrl(url: string): string {
  const comma = url.indexOf(",");
  if (comma < 0) return "";
  const meta = url.slice(0, comma);
  const body = url.slice(comma + 1);
  try {
    if (meta.includes(";base64")) return atob(body);
    return decodeURIComponent(body);
  } catch {
    return "";
  }
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

function isEmbedHost(url: string): boolean {
  const host = hostOf(url);
  return host === "youtube.com"
    || host === "youtu.be"
    || host === "youtube-nocookie.com"
    || host === "vimeo.com"
    || host === "player.vimeo.com";
}

function embedSrc(url: string): string {
  const host = hostOf(url);
  if (host !== "youtu.be" && host !== "youtube.com" && host !== "youtube-nocookie.com") {
    return url;
  }
  try {
    const parsed = new URL(url);
    if (host === "youtu.be") {
      const id = parsed.pathname.split("/").filter(Boolean)[0] || "";
      return id ? `https://www.youtube.com/embed/${id}?rel=0` : url;
    }
    if (parsed.pathname !== "/watch") return url;
    const id = parsed.searchParams.get("v") || "";
    if (!id) return url;
    const params = new URLSearchParams({ rel: "0" });
    const start = parsed.searchParams.get("start") || parsed.searchParams.get("t") || "";
    const end = parsed.searchParams.get("end") || "";
    if (start) params.set("start", start.replace(/s$/, ""));
    if (end) params.set("end", end);
    return `https://www.youtube.com/embed/${id}?${params.toString()}`;
  } catch {
    return url;
  }
}

export default function LessonClipPlayer({ url, title }: Props) {
  const playable = (url || "").trim();
  const dataSvg = playable.startsWith("data:image/svg+xml") ? svgFromDataUrl(playable) : "";
  const svgPath = playable.startsWith("/") && playable.split("?")[0].toLowerCase().endsWith(".svg");
  const [fetched, setFetched] = useState("");

  useEffect(() => {
    if (!svgPath) {
      setFetched("");
      return;
    }
    let cancelled = false;
    fetch(playable)
      .then((res) => (res.ok ? res.text() : ""))
      .then((text) => {
        if (!cancelled) setFetched(text);
      })
      .catch(() => {
        if (!cancelled) setFetched("");
      });
    return () => {
      cancelled = true;
    };
  }, [playable, svgPath]);

  if (!playable) return null;
  const svg = dataSvg || fetched;
  const frame = { width: "100%", height: "100%", border: 0, background: "#0b1220", display: "block" } as const;
  if (svg.includes("<svg")) {
    return (
      <div
        role="img"
        aria-label={title || "Lesson clip"}
        style={{ width: "100%", height: "100%", lineHeight: 0, background: "#0b1220" }}
        dangerouslySetInnerHTML={{ __html: sanitizeSvg(svg) }}
      />
    );
  }
  if (isEmbedHost(playable)) {
    return (
      <iframe
        title={title || "Lesson clip"}
        src={embedSrc(playable)}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        style={frame}
      />
    );
  }
  const lower = playable.toLowerCase();
  if (lower.startsWith("data:image/") || /\.(gif|webp)(\?|$)/.test(lower)) {
    return <img src={playable} alt={title || "Lesson clip"} style={{ ...frame, objectFit: "contain" }} />;
  }
  if (playable.startsWith("https://") || playable.startsWith("http://") || playable.startsWith("/")) {
    return <video src={playable} controls playsInline style={frame} />;
  }
  return null;
}

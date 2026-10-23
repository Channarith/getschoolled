"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const SEEN_KEY = "salareen.driversEdIntro.seen.v1";
const VIDEO_SRC = "/video/drivers-ed-intro.mp4";
const POSTER_SRC = "/video/drivers-ed-intro-poster.jpg";
const CREDITS_HREF = "/video/drivers-ed-intro-credits.txt";

const iconButton = {
  width: 48,
  height: 48,
  borderRadius: "50%",
  border: "2px solid rgba(255,255,255,.75)",
  background: "rgba(8,12,24,.55)",
  color: "#fff",
  display: "grid",
  placeItems: "center",
  cursor: "pointer",
  padding: 0,
} as const;

/** Text-free real-footage welcome that plays once per session, then hands off to the course. */
export function DriversEdIntro() {
  const [open, setOpen] = useState(false);
  const [needsTap, setNeedsTap] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let seen = false;
    try { seen = sessionStorage.getItem(SEEN_KEY) === "1"; } catch { /* private mode */ }
    if (!seen) setOpen(true);
  }, []);

  const finish = useCallback(() => {
    try { sessionStorage.setItem(SEEN_KEY, "1"); } catch { /* private mode */ }
    setLeaving(true);
    window.setTimeout(() => setOpen(false), 350);
  }, []);

  useEffect(() => {
    if (!open) return;
    const video = videoRef.current;
    if (!video) return;
    const attempt = video.play();
    if (attempt && typeof attempt.catch === "function") attempt.catch(() => setNeedsTap(true));
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") finish(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, finish]);

  if (!open) return null;

  return (
    <div
      data-testid="drivers-ed-intro"
      role="dialog"
      aria-modal="true"
      aria-label="Driver's Ed welcome video"
      style={{
        position: "fixed", inset: 0, zIndex: 2000, background: "#000",
        opacity: leaving ? 0 : 1, transition: "opacity .35s ease",
      }}
    >
      <video
        ref={videoRef}
        data-testid="drivers-ed-intro-video"
        src={VIDEO_SRC}
        poster={POSTER_SRC}
        muted
        playsInline
        autoPlay
        preload="auto"
        disablePictureInPicture
        onEnded={finish}
        onError={finish}
        style={{ width: "100%", height: "100%", objectFit: "cover", background: "#000" }}
      />
      {needsTap && (
        <button
          type="button"
          data-testid="drivers-ed-intro-play"
          aria-label="Play"
          onClick={() => { setNeedsTap(false); void videoRef.current?.play().catch(() => finish()); }}
          style={{ ...iconButton, position: "absolute", inset: 0, margin: "auto", width: 88, height: 88 }}
        >
          <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
        </button>
      )}
      <button
        type="button"
        data-testid="drivers-ed-intro-skip"
        aria-label="Skip intro"
        title="Skip"
        onClick={finish}
        style={{ ...iconButton, position: "absolute", right: "max(16px, env(safe-area-inset-right))", top: "max(16px, env(safe-area-inset-top))" }}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M5 5v14l9-7zM15 5h3v14h-3z" /></svg>
      </button>
      <a
        href={CREDITS_HREF}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Footage credits"
        title="Footage credits"
        style={{ ...iconButton, width: 28, height: 28, fontSize: 14, fontWeight: 700, opacity: 0.65, textDecoration: "none", position: "absolute", left: "max(16px, env(safe-area-inset-left))", bottom: "max(16px, env(safe-area-inset-bottom))" }}
      >
        i
      </a>
    </div>
  );
}

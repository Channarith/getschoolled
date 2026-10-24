"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { INTRO_SEEN_KEY, introPhase, tutorialStateFrom, type TutorialState } from "../lib/driversEdIntro";

const VIDEO_SRC = "/video/drivers-ed-intro.mp4";
const POSTER_SRC = "/video/drivers-ed-intro-poster.jpg";
const CREDITS_HREF = "/video/drivers-ed-intro-credits.txt";
// If the lesson frame never reports its tutorial (blocked, slow), do not leave the video waiting forever.
const NO_REPORT_MS = 8000;

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

function lessonFrames(): HTMLIFrameElement[] {
  return Array.from(document.querySelectorAll<HTMLIFrameElement>(".course-stage-embed iframe"));
}

function tellFrames(message: Record<string, unknown>) {
  for (const frame of lessonFrames()) frame.contentWindow?.postMessage(message, window.location.origin);
}

/**
 * Opening of the Driver's Ed demo, once per session:
 * 1. the tutorial shows first, with this video waiting (paused) behind it,
 * 2. when the tutorial is closed the video plays on top,
 * 3. when the video ends or is skipped the lesson page appears.
 */
export function DriversEdIntro() {
  const [active, setActive] = useState(false);
  const [tutorial, setTutorial] = useState<TutorialState>("pending");
  const [finished, setFinished] = useState(false);
  const [needsTap, setNeedsTap] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let seen = false;
    try { seen = sessionStorage.getItem(INTRO_SEEN_KEY) === "1"; } catch { /* private mode */ }
    if (!seen) setActive(true);
  }, []);

  const finish = useCallback(() => {
    try { sessionStorage.setItem(INTRO_SEEN_KEY, "1"); } catch { /* private mode */ }
    setFinished(true);
    setLeaving(true);
    tellFrames({ type: "sala-intro-done" });
    window.setTimeout(() => setActive(false), 350);
  }, []);

  // The lesson frame reports whether its tutorial is open or closed.
  useEffect(() => {
    if (!active) return;
    const ask = () => tellFrames({ type: "sala-intro-query" });
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      const state = tutorialStateFrom(event.data);
      if (state) setTutorial(state);
    };
    window.addEventListener("message", onMessage);
    ask();
    const frames = lessonFrames();
    for (const frame of frames) frame.addEventListener("load", ask);
    const giveUp = window.setTimeout(() => setTutorial((t) => (t === "pending" ? "closed" : t)), NO_REPORT_MS);
    return () => {
      window.removeEventListener("message", onMessage);
      for (const frame of frames) frame.removeEventListener("load", ask);
      window.clearTimeout(giveUp);
    };
  }, [active]);

  const phase = introPhase(tutorial, finished);

  // Play only after the tutorial; pause again if it is reopened.
  useEffect(() => {
    if (!active) return;
    const video = videoRef.current;
    if (!video) return;
    if (phase === "hold") {
      video.pause();
      return;
    }
    if (phase !== "play") return;
    const reduced = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced && video.currentTime === 0) {
      setNeedsTap(true);
      return;
    }
    const attempt = video.play();
    if (attempt && typeof attempt.catch === "function") attempt.catch(() => setNeedsTap(true));
  }, [active, phase]);

  // While the video waits, the lesson frame sits above it with a see-through background.
  useEffect(() => {
    if (!active) return;
    const hold = phase === "hold";
    document.body.classList.toggle("drivers-ed-hold", hold);
    return () => document.body.classList.remove("drivers-ed-hold");
  }, [active, phase]);

  useEffect(() => {
    if (!active) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape" && phase === "play") finish(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, phase, finish]);

  if (!active) return null;

  const playing = phase === "play" || phase === "done";

  return (
    <div
      data-testid="drivers-ed-intro"
      data-phase={phase}
      role={playing ? "dialog" : undefined}
      aria-modal={playing ? true : undefined}
      aria-label="Driver's Ed welcome video"
      aria-hidden={playing ? undefined : true}
      style={{
        position: "fixed", inset: 0, zIndex: playing ? 2000 : 1, background: "#000",
        pointerEvents: playing ? "auto" : "none",
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
        preload="auto"
        disablePictureInPicture
        tabIndex={-1}
        onEnded={finish}
        onError={finish}
        style={{ width: "100%", height: "100%", objectFit: "cover", background: "#000" }}
      />
      {playing && needsTap && (
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
      {playing && (
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
      )}
      {playing && (
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
      )}
    </div>
  );
}

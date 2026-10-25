"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { INTRO_SEEN_KEY, introPhase, tutorialStateFrom, type TutorialState } from "../lib/driversEdIntro";

const VIDEO_SRC = "/video/drivers-ed-intro.mp4";
const POSTER_SRC = "/video/drivers-ed-intro-poster.jpg";
const CREDITS_HREF = "/video/drivers-ed-intro-credits.txt";
// If the lesson frame never reports its tutorial (blocked, slow), do not leave the video waiting forever.
const NO_REPORT_MS = 8000;
// The opening scene never holds the learner longer than this: the lesson starts by itself (there is no Next or Skip button).
const MAX_INTRO_MS = 15000;

const creditsLink = {
  width: 28,
  height: 28,
  borderRadius: "50%",
  border: "2px solid rgba(255,255,255,.75)",
  background: "rgba(8,12,24,.55)",
  color: "#fff",
  display: "grid",
  placeItems: "center",
  fontSize: 14,
  fontWeight: 700,
  opacity: 0.65,
  textDecoration: "none",
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
 * 2. when the tutorial is closed the video plays as the opening scene BEHIND the lesson page: the combined widget (camera,
 *    voice, timer) and Sala are already there, on top of it,
 * 3. when the video ends (or after MAX_INTRO_MS) the lesson starts by itself. There is no Next or Skip button.
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

  const phase = introPhase(tutorial, finished);

  // The lesson frame reports whether its tutorial is open or closed.
  useEffect(() => {
    if (!active) return;
    const ask = () => tellFrames({ type: "sala-intro-query" });
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      const state = tutorialStateFrom(event.data);
      if (state) setTutorial(state);
      // Autoplay was blocked: the learner tapped Sala ("Tap to start") inside the lesson frame.
      if (event.data && typeof event.data === "object" && (event.data as { type?: string }).type === "sala-intro-tap") {
        setNeedsTap(false);
        void videoRef.current?.play().catch(() => finish());
      }
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
  }, [active, finish]);

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

  // Blocked autoplay: Sala (in the lesson frame) shows one clear "Tap to start", not a Next button.
  useEffect(() => {
    if (needsTap) tellFrames({ type: "sala-intro-needs-tap" });
  }, [needsTap]);

  // The opening scene is short: whatever happens, the lesson starts by itself after MAX_INTRO_MS of playing.
  useEffect(() => {
    if (!active || phase !== "play" || needsTap) return;
    const timer = window.setTimeout(finish, MAX_INTRO_MS);
    return () => window.clearTimeout(timer);
  }, [active, phase, needsTap, finish]);

  // While the video waits, the lesson frame sits above it with a see-through background.
  useEffect(() => {
    if (!active) return;
    const behind = phase !== "done";
    document.body.classList.toggle("drivers-ed-hold", behind);
    return () => document.body.classList.remove("drivers-ed-hold");
  }, [active, phase]);

  if (!active) return null;

  return (
    <div
      data-testid="drivers-ed-intro"
      data-phase={phase}
      aria-hidden
      style={{
        position: "fixed", inset: 0, zIndex: 1, background: "#000",
        pointerEvents: "none",
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
      {phase === "play" && (
        <a
          href={CREDITS_HREF}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Footage credits"
          title="Footage credits"
          style={{ ...creditsLink, pointerEvents: "auto", position: "fixed", right: "max(16px, env(safe-area-inset-right))", bottom: "max(16px, env(safe-area-inset-bottom))", zIndex: 2001 }}
        >
          i
        </a>
      )}
    </div>
  );
}

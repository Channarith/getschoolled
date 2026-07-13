"use client";

// Global intro sequence: a full-screen branded animation + synthesized jingle.
// Auto-plays once per browser session (visual-only, since audio autoplay is
// blocked without a gesture) and can be replayed from Settings via
// PLAY_INTRO_EVENT (a user gesture, so the jingle plays with sound).

import { useCallback, useEffect, useRef, useState } from "react";

import {
  pickRandomVariant, variantById, type IntroVariant,
} from "../lib/introAnimations";
import { IntroSong } from "../lib/introSong";

export const PLAY_INTRO_EVENT = "aoep:play-intro";
export const INTRO_AUTOPLAY_KEY = "aoep_intro_autoplay";   // 'off' disables session autoplay

/** Fire from anywhere (e.g. Settings) to (re)play the intro, optionally a specific variant. */
export function playIntro(variantId?: string): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(PLAY_INTRO_EVENT, { detail: { variant: variantId } }));
  }
}

const DURATION = 5200;
const SESSION_KEY = "aoep_intro_shown";

export default function IntroSequence() {
  const [run, setRun] = useState<{ v: IntroVariant; audio: boolean; key: number } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const logoRef = useRef<HTMLImageElement | null>(null);
  const songRef = useRef<IntroSong | null>(null);
  const rafRef = useRef(0);
  const keyRef = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const img = new Image();
    img.src = "/logo-mark.webp";
    logoRef.current = img;
  }, []);

  const stop = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = 0;
    songRef.current?.stop();
    songRef.current = null;
    setRun(null);
  }, []);

  const start = useCallback((variantId: string | undefined, audio: boolean) => {
    keyRef.current += 1;
    setRun({ v: variantById(variantId) ?? pickRandomVariant(), audio, key: keyRef.current });
  }, []);

  // Auto-play once per session (skipped when reduced-motion or disabled).
  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;
    let timer = 0;
    try {
      const off = localStorage.getItem(INTRO_AUTOPLAY_KEY) === "off";
      const shown = sessionStorage.getItem(SESSION_KEY) === "1";
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      if (!off && !shown && !reduce) {
        sessionStorage.setItem(SESSION_KEY, "1");
        timer = window.setTimeout(() => { if (!cancelled) start(undefined, false); }, 350);
      }
    } catch { /* storage unavailable */ }
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [start]);

  // Replay requests (from Settings) — a user gesture, so sound is allowed.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onPlay = (e: Event) => {
      const detail = (e as CustomEvent).detail as { variant?: string } | undefined;
      start(detail?.variant, true);
    };
    window.addEventListener(PLAY_INTRO_EVENT, onPlay as EventListener);
    return () => window.removeEventListener(PLAY_INTRO_EVENT, onPlay as EventListener);
  }, [start]);

  // Drive the current animation.
  useEffect(() => {
    if (!run) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) { stop(); return; }

    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const resize = () => {
      canvas.width = Math.round(window.innerWidth * dpr);
      canvas.height = Math.round(window.innerHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    if (run.audio) { const song = new IntroSong(); songRef.current = song; song.play(run.v.melody); }

    const S: Record<string, unknown> = {};
    const t0 = performance.now();
    const frame = (now: number) => {
      const p = Math.min(1, (now - t0) / DURATION);
      try { run.v.render(ctx, window.innerWidth, window.innerHeight, p, logoRef.current, S); } catch { /* keep the app alive */ }
      if (p >= 1) { stop(); return; }
      rafRef.current = requestAnimationFrame(frame);
    };
    rafRef.current = requestAnimationFrame(frame);

    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") stop(); };
    window.addEventListener("keydown", onKey);

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("keydown", onKey);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      songRef.current?.stop();
      songRef.current = null;
    };
  }, [run, stop]);

  if (!run) return null;
  return (
    <div
      role="dialog"
      aria-label="Intro animation"
      style={{
        position: "fixed", inset: 0, zIndex: 100000, background: "#04030c",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      <canvas ref={canvasRef} style={{ width: "100vw", height: "100vh", display: "block" }} />
      <div style={{
        position: "fixed", bottom: 22, left: "50%", transform: "translateX(-50%)",
        color: "rgba(226,232,255,0.75)", fontSize: 13, letterSpacing: 1, textTransform: "uppercase",
        pointerEvents: "none",
      }}>
        {run.v.name}
      </div>
      <button
        onClick={stop}
        style={{
          position: "fixed", top: 18, right: 18, zIndex: 100001,
          background: "rgba(255,255,255,0.12)", color: "#fff", border: "1px solid rgba(255,255,255,0.25)",
          borderRadius: 999, padding: "8px 18px", fontSize: 14, cursor: "pointer", backdropFilter: "blur(6px)",
        }}
      >
        Skip ⏭
      </button>
    </div>
  );
}

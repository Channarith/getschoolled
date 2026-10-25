"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { AUTH_EVENT, getToken } from "../lib/api";
import OrbitalMascotStage, { type MascotSpotlight } from "./OrbitalMascotStage";
import type { Expression } from "./mascot3d/expressions";
import type { ClipName } from "./MascotMeshy";
import { landingClipUrl } from "../lib/cloneVoice";
import landingVoiceLines from "../lib/landingVoiceLines.json";

// The spoken lines live in landingVoiceLines.json so the pre-rendered clips (scripts/render_landing_voice.py) and this
// component always read the same text.
const LANDING_LANG = "en";
const SPOKEN: Record<string, string> = Object.fromEntries(landingVoiceLines.lines.map((l) => [l.id, l.text]));

/**
 * DN "Dark Navy" landing hero — modeled 1:1 on the DN mockup.
 *
 * Layout (desktop, >= 980px):
 *   ┌─────────────────────────────────────────────────────────┐
 *   │  LEFT (50%)                     RIGHT (50%)             │
 *   │  "AI Precision."                ┌───────────────────┐   │
 *   │  "Human Warmth."                │   📖     👁️       │   │
 *   │  short subtitle                 │       🪷          │   │
 *   │  [Start free class]  ghost      │   💼     🎧       │   │
 *   │                                 │        🎓          │   │
 *   │                                 │  (orbital tiles   │   │
 *   │                                 │   rotate CW,      │   │
 *   │                                 │   hover for prev) │   │
 *   │                                 └───────────────────┘   │
 *   └─────────────────────────────────────────────────────────┘
 *   │  [One tutor per student] [Learn by playing] [Live classes]  │
 *
 * On narrow viewports the two columns stack: headline on top, orbital
 * stage below, then the feature cards. The orbital widget shrinks via
 * `transform: scale()` driven by a container-query-ish media rule.
 */

const FEATURES: Array<{
  id: string;
  icon: string;
  title: string;
  body: string;
  line: string;
  clip: ClipName;
  expression: Expression;
}> = [
  {
    id: "tutor",
    icon: "👤",
    title: "One tutor per student",
    body: "A dedicated AI tutor that adapts to how you learn.",
    line: SPOKEN.tutor,
    clip: "Big_Wave_Hello",
    expression: "cute",
  },
  {
    id: "play",
    icon: "🎮",
    title: "Learn by playing",
    body: "Adaptive games and webcam vision labs for every age.",
    line: SPOKEN.play,
    clip: "Indoor_Swing",
    expression: "excited",
  },
  {
    id: "live",
    icon: "💬",
    title: "Live human-paced classes",
    body: "Real teachers, real conversations, your pace.",
    line: SPOKEN.live,
    clip: "Confident_Strut",
    expression: "curious",
  },
];

function pickVoice(): SpeechSynthesisVoice | null {
  const synth = window.speechSynthesis;
  if (!synth) return null;
  const voices = synth.getVoices();
  return (
    voices.find((v) => /samantha|karen|moira|serena/i.test(v.name)) ??
    voices.find((v) => v.lang.toLowerCase().startsWith("en")) ??
    null
  );
}

// null until the browser has been asked, so a signed-in visitor never sees the
// Login / demo buttons flash before they disappear.
function useSignedIn(): boolean | null {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  useEffect(() => {
    const sync = () => setSignedIn(Boolean(getToken()));
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return signedIn;
}

export default function DNLandingHero() {
  const signedIn = useSignedIn();
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [pinnedId, setPinnedId] = useState<string | null>(null);
  const [reduced, setReduced] = useState(false);
  const enterTimer = useRef<number | null>(null);
  const leaveTimer = useRef<number | null>(null);
  const spokenFor = useRef<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const userActive = useRef(false);
  const activeId = hoverId ?? pinnedId;
  const spotlight: MascotSpotlight | null = useMemo(() => {
    const feature = FEATURES.find((item) => item.id === activeId);
    if (!feature) return null;
    return {
      id: feature.id,
      title: feature.title,
      line: feature.line,
      clip: feature.clip,
      expression: feature.expression,
    };
  }, [activeId]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setPinnedId(null);
      setHoverId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Autoplay rule: nothing speaks until the visitor has pressed, tapped or typed something on the page.
  useEffect(() => {
    userActive.current = Boolean(
      (navigator as Navigator & { userActivation?: { hasBeenActive: boolean } }).userActivation?.hasBeenActive,
    );
    const mark = () => {
      userActive.current = true;
    };
    const opts = { capture: true, passive: true } as const;
    window.addEventListener("pointerdown", mark, opts);
    window.addEventListener("keydown", mark, opts);
    window.addEventListener("touchstart", mark, opts);
    return () => {
      window.removeEventListener("pointerdown", mark, opts);
      window.removeEventListener("keydown", mark, opts);
      window.removeEventListener("touchstart", mark, opts);
    };
  }, []);

  function stopAudio() {
    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
    }
    window.speechSynthesis?.cancel();
  }

  // Last resort only: used when a pre-rendered clip is missing or fails to load.
  function speakWithBrowserVoice(line: string) {
    const synth = window.speechSynthesis;
    if (!synth) return;
    const utter = new SpeechSynthesisUtterance(line);
    utter.rate = 1.02;
    utter.pitch = 1.08;
    const voice = pickVoice();
    if (voice) utter.voice = voice;
    synth.cancel();
    synth.speak(utter);
  }

  useEffect(() => {
    if (!spotlight) {
      spokenFor.current = null;
      stopAudio();
      return;
    }
    if (spokenFor.current !== spotlight.id) stopAudio();
    // Hover shows the line. Speech needs a prior user gesture and waits for a click when motion is reduced,
    // and starts once per topic so a pin does not repeat it.
    const shouldSpeak = pinnedId === spotlight.id || (!reduced && userActive.current);
    if (!shouldSpeak || spokenFor.current === spotlight.id) return;
    const topicId = spotlight.id;
    const line = spotlight.line;
    let alive = true;
    const timer = window.setTimeout(async () => {
      if (!alive) return;
      spokenFor.current = topicId;
      const url = await landingClipUrl(LANDING_LANG, line).catch(() => null);
      if (!alive) return;
      if (!url) {
        speakWithBrowserVoice(line);
        return;
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        if (audioRef.current === audio) audioRef.current = null;
      };
      audio.onerror = () => {
        if (audioRef.current !== audio) return;
        audioRef.current = null;
        speakWithBrowserVoice(line);
      };
      try {
        await audio.play();
      } catch (err) {
        // Blocked by the browser's autoplay policy: stay silent (the text is on screen).
        if (audioRef.current === audio && !(err instanceof DOMException && err.name === "NotAllowedError")) {
          audioRef.current = null;
          speakWithBrowserVoice(line);
        }
      }
    }, 60);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spotlight, pinnedId, reduced]);

  useEffect(() => {
    const onHide = () => stopAudio();
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      if (enterTimer.current) window.clearTimeout(enterTimer.current);
      if (leaveTimer.current) window.clearTimeout(leaveTimer.current);
      stopAudio();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function clearTimers() {
    if (enterTimer.current) window.clearTimeout(enterTimer.current);
    if (leaveTimer.current) window.clearTimeout(leaveTimer.current);
    enterTimer.current = null;
    leaveTimer.current = null;
  }

  function preview(id: string) {
    clearTimers();
    enterTimer.current = window.setTimeout(() => setHoverId(id), 160);
  }

  function release() {
    if (enterTimer.current) window.clearTimeout(enterTimer.current);
    enterTimer.current = null;
    leaveTimer.current = window.setTimeout(() => setHoverId(null), 180);
  }

  function pin(id: string) {
    clearTimers();
    setHoverId(id);
    setPinnedId((current) => (current === id ? null : id));
  }

  return (
    <main className="dn-landing">
      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="dn-landing-hero">
        <div className="dn-landing-hero-copy">
          <h1 className="dn-landing-title">
            AI Precision.
            <br />
            Human <em>Warmth.</em>
          </h1>
          <p className="dn-landing-subtitle">
            Salareen pairs every learner with a tutor that adapts to how
            they think.
          </p>
          {/* CTA row: primary -> Login (/create account), ghost ->
              /demo (the three-demo picker: Solo AI, On-the-Go, Vision
              Play). The old "Start free class" label pushed a signed-in
              class flow that doesn't exist for guests; "Login" matches
              what the button actually does. "See how it works" used to
              point at /our-story, but Our Story is a brand page, not a
              product tour - the tour is /demo. */}
          {signedIn === false && (
            <div className="dn-landing-cta-row" data-testid="landing-guest-cta">
              <Link href="/login" className="btn-primary">
                Login
              </Link>
              <Link href="/demo" className="link-ghost">
                See how it works
              </Link>
            </div>
          )}
        </div>

        <div className="dn-landing-hero-stage">
          <OrbitalMascotStage spotlight={spotlight} />
        </div>
      </section>

      {/* ── Feature cards ────────────────────────────────────────────── */}
      <section className="dn-landing-features" aria-label="What Salareen does">
        {FEATURES.map((f) => {
          const pinned = pinnedId === f.id;
          const active = activeId === f.id;
          return (
            <button
              key={f.id}
              type="button"
              className={`dn-landing-feature-card${active ? " is-active" : ""}`}
              aria-pressed={pinned}
              aria-controls="dn-mascot-speech"
              data-testid={`feature-${f.id}`}
              onMouseEnter={() => preview(f.id)}
              onMouseLeave={release}
              onFocus={() => {
                clearTimers();
                setHoverId(f.id);
              }}
              onBlur={release}
              onClick={() => pin(f.id)}
            >
              <div className="dn-landing-feature-icon" aria-hidden>
                {f.icon}
              </div>
              <div className="dn-landing-feature-body">
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </div>
            </button>
          );
        })}
      </section>
    </main>
  );
}

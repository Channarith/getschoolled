"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { AUTH_EVENT, getToken } from "../lib/api";
import OrbitalMascotStage, { type MascotSpotlight } from "./OrbitalMascotStage";
import type { Expression } from "./mascot3d/expressions";
import type { ClipName } from "./MascotMeshy";

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
    line: "You get one tutor, just for you. I notice how you think, then I change the lesson so it fits.",
    clip: "Big_Wave_Hello",
    expression: "cute",
  },
  {
    id: "play",
    icon: "🎮",
    title: "Learn by playing",
    body: "Adaptive games and webcam vision labs for every age.",
    line: "Learning feels like play here. Adaptive games and webcam labs meet you at any age.",
    clip: "Indoor_Swing",
    expression: "excited",
  },
  {
    id: "live",
    icon: "💬",
    title: "Live human-paced classes",
    body: "Real teachers, real conversations, your pace.",
    line: "Live class moves with you. A real teacher talks with you, and I stay right beside you.",
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
    const synth = window.speechSynthesis;
    if (!synth) return;
    const warm = () => synth.getVoices();
    warm();
    synth.addEventListener("voiceschanged", warm);
    return () => synth.removeEventListener("voiceschanged", warm);
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

  useEffect(() => {
    const synth = window.speechSynthesis;
    if (!spotlight) {
      spokenFor.current = null;
      synth?.cancel();
      return;
    }
    // Hover shows the line. Speech waits for a click when motion is reduced,
    // and otherwise starts once per topic so a pin does not repeat it.
    const shouldSpeak = pinnedId === spotlight.id || !reduced;
    if (!shouldSpeak || spokenFor.current === spotlight.id) return;
    if (!synth) return;
    const topicId = spotlight.id;
    const utter = new SpeechSynthesisUtterance(spotlight.line);
    utter.rate = 1.02;
    utter.pitch = 1.08;
    const voice = pickVoice();
    if (voice) utter.voice = voice;
    let alive = true;
    synth.cancel();
    const timer = window.setTimeout(() => {
      if (!alive) return;
      spokenFor.current = topicId;
      synth.speak(utter);
    }, 60);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [spotlight, pinnedId, reduced]);

  useEffect(() => {
    return () => {
      if (enterTimer.current) window.clearTimeout(enterTimer.current);
      if (leaveTimer.current) window.clearTimeout(leaveTimer.current);
      window.speechSynthesis?.cancel();
    };
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

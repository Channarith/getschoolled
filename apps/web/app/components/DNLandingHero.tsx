"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AUTH_EVENT, getToken } from "../lib/api";
import OrbitalMascotStage from "./OrbitalMascotStage";

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

const FEATURES = [
  {
    icon: "👤",
    title: "One tutor per student",
    body: "A dedicated AI tutor that adapts to how you learn.",
  },
  {
    icon: "🎮",
    title: "Learn by playing",
    body: "Adaptive games and webcam vision labs for every age.",
  },
  {
    icon: "💬",
    title: "Live human-paced classes",
    body: "Real teachers, real conversations, your pace.",
  },
];

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
          <OrbitalMascotStage />
        </div>
      </section>

      {/* ── Feature cards ────────────────────────────────────────────── */}
      <section className="dn-landing-features">
        {FEATURES.map((f) => (
          <div key={f.title} className="dn-landing-feature-card">
            <div className="dn-landing-feature-icon" aria-hidden>
              {f.icon}
            </div>
            <div className="dn-landing-feature-body">
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}

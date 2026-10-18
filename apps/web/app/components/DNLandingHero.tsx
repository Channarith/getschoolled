"use client";

import Link from "next/link";
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

export default function DNLandingHero() {
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
          <div className="dn-landing-cta-row">
            <Link href="/class" className="btn-primary">
              Start free class
            </Link>
            <Link href="/our-story" className="link-ghost">
              See how it works
            </Link>
          </div>
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

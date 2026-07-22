"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getToken } from "../lib/api";
import { useFlags } from "../lib/flags";
import {
  SALES_DEMO_COURSES,
  SALES_DEMO_FEATURES,
  SALES_DEMO_FLAGS,
} from "../lib/salesDemo";

export default function SalesDemoPage() {
  const router = useRouter();
  const { flags, ready } = useFlags();
  const [signedIn, setSignedIn] = useState<boolean | null>(null);

  useEffect(() => {
    const authenticated = Boolean(getToken());
    setSignedIn(authenticated);
    if (!authenticated) router.replace("/login");
  }, [router]);

  const enabled = (key: string) => !ready || flags[key] !== false;
  const demoEnabled = enabled(SALES_DEMO_FLAGS.enabled);
  const features = SALES_DEMO_FEATURES.filter((feature) => enabled(feature.flagKey));

  useEffect(() => {
    if (signedIn && ready && !demoEnabled) router.replace("/");
  }, [demoEnabled, ready, router, signedIn]);

  if (signedIn !== true || (ready && !demoEnabled)) {
    return <main style={{ padding: 40, textAlign: "center" }}>Loading Sales Demo…</main>;
  }

  return (
    <main style={{ maxWidth: 1180, margin: "0 auto", padding: "34px 22px 70px" }}>
      <style>{`
        @keyframes sales-demo-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
        @keyframes sales-demo-enter {
          from { opacity: 0; transform: translateY(24px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .sales-demo-card { animation: sales-demo-enter .45s ease both; transition: transform .2s ease; }
        .sales-demo-card:hover { transform: translateY(-4px) scale(1.01); }
      `}</style>

      <section
        style={{
          border: "1px solid rgba(165,180,252,.28)",
          borderRadius: 28,
          padding: "52px 24px",
          textAlign: "center",
          background:
            "radial-gradient(circle at top, rgba(99,102,241,.34), transparent 54%), rgba(7,8,15,.9)",
        }}
      >
        <div style={{ fontSize: 58, animation: "sales-demo-float 3s ease-in-out infinite" }}>✨</div>
        <span className="theme-badge">SALES DEMO</span>
        <h1 className="theme-title glow" style={{ margin: "14px auto 8px", fontSize: 48 }}>
          Salareen
        </h1>
        <p className="theme-subtitle glow" style={{ margin: "0 auto" }}>
          AI-powered education for courses, coaching, compliance, and continuous learning.
        </p>
        <div style={{ marginTop: 22 }}>
          <Link href="/"><button type="button">← Back to app</button></Link>
        </div>
      </section>

      {enabled(SALES_DEMO_FLAGS.featuredCourses) ? (
        <section style={{ marginTop: 34 }}>
          <h2>Featured courses</h2>
          <p className="muted">Workplace-ready learning paths powered by adaptive AI.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 16 }}>
            {SALES_DEMO_COURSES.map((course, index) => (
              <Link key={course.id} href="/browse" style={{ textDecoration: "none", color: "inherit" }}>
                <article
                  className="card sales-demo-card"
                  style={{
                    minHeight: 220,
                    padding: 20,
                    color: "#fff",
                    background: `linear-gradient(145deg, ${course.colors[0]}, ${course.colors[1]})`,
                    animationDelay: `${index * 70}ms`,
                  }}
                >
                  <div style={{ fontSize: 40 }}>{course.emoji}</div>
                  <small style={{ opacity: 0.8 }}>{course.category} · {course.duration}</small>
                  <h3>{course.title}</h3>
                  <p style={{ opacity: 0.82 }}>{course.description}</p>
                </article>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {features.length ? (
        <section style={{ marginTop: 38 }}>
          <h2>What makes Salareen different</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 16 }}>
            {features.map((feature, index) => (
              <Link key={feature.id} href={feature.href} style={{ textDecoration: "none", color: "inherit" }}>
                <article
                  className="card sales-demo-card"
                  style={{ minHeight: 190, padding: 20, animationDelay: `${280 + index * 70}ms` }}
                >
                  <div style={{ fontSize: 36 }}>{feature.emoji}</div>
                  <h3 style={{ marginBottom: 2 }}>{feature.title}</h3>
                  <strong style={{ color: "#a5b4fc", fontSize: 13 }}>{feature.subtitle}</strong>
                  <p className="muted">{feature.description}</p>
                </article>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {enabled(SALES_DEMO_FLAGS.fullAppCta) ? (
        <section style={{ textAlign: "center", marginTop: 42 }}>
          <Link href="/browse">
            <button type="button" className="theme-btn" style={{ background: "#6366f1", color: "#fff", padding: "15px 24px" }}>
              🚀 Explore the full platform
            </button>
          </Link>
        </section>
      ) : null}
    </main>
  );
}

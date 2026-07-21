"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const DEMO_COURSES = [
  { id: "harassment", title: "Sexual Harassment Prevention", category: "Compliance", emoji: "🛡️", minutes: 45, segments: 8, from: "#6366f1", to: "#8b5cf6", desc: "Understand workplace rights, recognize harassment, and build a respectful culture." },
  { id: "drivers-ed", title: "Driver's Education", category: "Safety", emoji: "🚗", minutes: 60, segments: 12, from: "#f59e0b", to: "#f97316", desc: "Master road rules, safe driving, and defensive driving strategies." },
  { id: "fire-safety", title: "Fire Safety", category: "Workplace Safety", emoji: "🔥", minutes: 30, segments: 6, from: "#ef4444", to: "#dc2626", desc: "Evacuation procedures, fire prevention, and extinguisher use." },
  { id: "food-safety", title: "Food Safety Handler Certification", category: "Food & Beverage", emoji: "🍽️", minutes: 45, segments: 9, from: "#10b981", to: "#059669", desc: "Food handling, storage, hygiene, and contamination prevention." },
  { id: "osha", title: "OSHA Safety Training", category: "Workplace Safety", emoji: "⚠️", minutes: 60, segments: 10, from: "#f97316", to: "#ea580c", desc: "Federal safety regulations, hazard identification, and compliance." },
];

const FEATURES = [
  { id: "ai", emoji: "🤖", title: "Solo AI Session", sub: "Ask Theodore anything", desc: "1:1 AI tutor that adapts to your pace, answers questions instantly, and guides you through any course.", color: "#6366f1", href: "/class" },
  { id: "drive", emoji: "🎧", title: "On-the-Go Mode", sub: "Learn hands-free", desc: "Full audio-only Drive Mode. Learn while commuting, exercising, or anywhere without a screen.", color: "#f59e0b", href: "/drive" },
  { id: "arcade", emoji: "🎮", title: "Arcade Games", sub: "Test your knowledge", desc: "Spot-the-difference, creature catch, card match — instant games that reinforce learning.", color: "#10b981", href: "/arcade" },
  { id: "lang", emoji: "🗣️", title: "Language Practice", sub: "Speak with confidence", desc: "AI pronunciation coach listens, scores your accent, and gives instant real-time feedback.", color: "#ec4899", href: "/languages" },
];

export default function DemoPage() {
  const [visible, setVisible] = useState(false);
  useEffect(() => { const t = setTimeout(() => setVisible(true), 50); return () => clearTimeout(t); }, []);

  return (
    <>
      <style>{`
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.6; }
          50% { transform: scale(1.4); opacity: 0; }
          100% { transform: scale(1); opacity: 0.6; }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-8px); }
        }
        @keyframes fade-up {
          from { opacity: 0; transform: translateY(32px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes cta-pulse {
          0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(99,102,241,0.4); }
          50% { transform: scale(1.02); box-shadow: 0 0 0 12px rgba(99,102,241,0); }
        }
        .demo-card-enter {
          animation: fade-up 0.5s ease forwards;
          opacity: 0;
        }
        .demo-cta { animation: cta-pulse 2s ease-in-out infinite; }
        .demo-float { animation: float 3s ease-in-out infinite; }
        .demo-card:hover { transform: translateY(-4px) scale(1.02); }
        .demo-card { transition: transform 0.2s ease; }
        .feature-card:hover { background: rgba(255,255,255,0.08) !important; transform: translateY(-2px); }
        .feature-card { transition: background 0.2s, transform 0.2s; }
      `}</style>

      <div style={{ background: "#07080f", minHeight: "100vh", color: "#fff", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>

        {/* Hero */}
        <div style={{ textAlign: "center", padding: "80px 20px 48px", position: "relative" }}>
          {/* Pulse ring */}
          <div style={{ position: "relative", display: "inline-block", marginBottom: 24 }}>
            <div style={{ position: "absolute", inset: -24, borderRadius: "50%", border: "2px solid #6366f1", animation: "pulse-ring 2s ease-in-out infinite" }} />
            <div className="demo-float" style={{ width: 80, height: 80, borderRadius: "50%", background: "rgba(99,102,241,0.15)", border: "2px solid rgba(99,102,241,0.4)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36 }}>
              🎓
            </div>
          </div>

          <div style={{ display: "inline-block", background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.35)", borderRadius: 20, padding: "6px 20px", fontSize: 11, fontWeight: 800, letterSpacing: 2, color: "#a5b4fc", marginBottom: 20 }}>
            ✨ SALES DEMO
          </div>

          <h1 style={{ fontSize: "clamp(36px,6vw,64px)", fontWeight: 900, margin: "0 0 12px", letterSpacing: -1, background: "linear-gradient(135deg,#fff 0%,#a5b4fc 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Salareen
          </h1>
          <p style={{ fontSize: 18, color: "#a5b4fc", fontWeight: 600, margin: "0 0 8px" }}>AI-Powered Education Platform</p>
          <p style={{ fontSize: 14, color: "rgba(255,255,255,0.4)", maxWidth: 480, margin: "0 auto 36px" }}>
            Explore the future of workplace compliance training — AI-driven, on-the-go, and actually engaging.
          </p>

          <a href="/drive" className="demo-cta" style={{ display: "inline-block", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", borderRadius: 16, padding: "16px 40px", fontSize: 17, fontWeight: 800, color: "#fff", textDecoration: "none", letterSpacing: 0.3 }}>
            🚀  Start Demo
          </a>
        </div>

        {/* Courses */}
        <div style={{ padding: "0 20px 48px", maxWidth: 1200, margin: "0 auto" }}>
          <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Featured Courses</h2>
          <p style={{ color: "rgba(255,255,255,0.4)", fontSize: 13, marginBottom: 24 }}>5 compliance essentials — each fully AI-powered</p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: 16 }}>
            {DEMO_COURSES.map((c, i) => (
              <Link key={c.id} href="/drive" style={{ textDecoration: "none" }}>
                <div
                  className="demo-card demo-card-enter"
                  style={{
                    background: `linear-gradient(135deg,${c.from},${c.to})`,
                    borderRadius: 20,
                    padding: 24,
                    minHeight: 220,
                    cursor: "pointer",
                    animationDelay: `${i * 80}ms`,
                    display: "flex", flexDirection: "column", justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>{c.emoji}</div>
                    <div style={{ display: "inline-block", background: "rgba(0,0,0,0.22)", borderRadius: 10, padding: "3px 10px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.9)", letterSpacing: 0.5, marginBottom: 10 }}>{c.category}</div>
                    <div style={{ fontSize: 16, fontWeight: 800, color: "#fff", lineHeight: 1.3, marginBottom: 8 }}>{c.title}</div>
                    <div style={{ fontSize: 12, color: "rgba(255,255,255,0.72)", lineHeight: 1.5 }}>{c.desc}</div>
                  </div>
                  <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
                    <span style={{ fontSize: 11, color: "rgba(255,255,255,0.7)", fontWeight: 600 }}>⏱ {c.minutes} min</span>
                    <span style={{ fontSize: 11, color: "rgba(255,255,255,0.7)", fontWeight: 600 }}>📚 {c.segments} segments</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Features */}
        <div style={{ padding: "0 20px 80px", maxWidth: 1200, margin: "0 auto" }}>
          <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>What Makes Salareen Different</h2>
          <p style={{ color: "rgba(255,255,255,0.4)", fontSize: 13, marginBottom: 24 }}>Four features your team will actually use</p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(240px,1fr))", gap: 16 }}>
            {FEATURES.map((f, i) => (
              <Link key={f.id} href={f.href} style={{ textDecoration: "none" }}>
                <div
                  className="feature-card demo-card-enter"
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: 20,
                    padding: 24,
                    minHeight: 190,
                    cursor: "pointer",
                    animationDelay: `${300 + i * 80}ms`,
                    position: "relative",
                    overflow: "hidden",
                  }}
                >
                  <div style={{ position: "absolute", top: 0, right: 0, width: 80, height: 80, borderRadius: "50%", background: f.color, opacity: 0.08, transform: "translate(20px,-20px)" }} />
                  <div style={{ fontSize: 36, marginBottom: 14 }}>{f.emoji}</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "#fff", marginBottom: 4 }}>{f.title}</div>
                  <div style={{ fontSize: 12, color: f.color, fontWeight: 700, marginBottom: 10 }}>{f.sub}</div>
                  <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", lineHeight: 1.5 }}>{f.desc}</div>
                  <div style={{ position: "absolute", bottom: 20, right: 20, width: 8, height: 8, borderRadius: "50%", background: f.color }} />
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{ textAlign: "center", paddingBottom: 40, color: "rgba(255,255,255,0.2)", fontSize: 12 }}>
          Salareen · AI Education Platform · sales@salareen.com
        </div>
      </div>
    </>
  );
}

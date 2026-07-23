"use client";

// Pro Scenarios — "What would you do?" drills for professional / corporate courses.
// Workplace compliance, safety, privacy, ethics, security, and trade scenarios.

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  PRO_SCENARIOS, TRACK_LABELS, scenariosForTrack,
  type ProScenario, type ProTrack,
} from "../../lib/professionalScenarios";

type Phase = "idle" | "playing" | "done";

export default function ProScenarios() {
  const [track, setTrack] = useState<ProTrack | "all">("all");
  const [phase, setPhase] = useState<Phase>("idle");
  const [pool, setPool] = useState<ProScenario[]>([]);
  const [idx, setIdx] = useState(0);
  const [score, setScore] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [answered, setAnswered] = useState(false);
  const [best, setBest] = useState(0);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("track");
    if (q && q in TRACK_LABELS) setTrack(q as ProTrack);
    try { setBest(Number(localStorage.getItem("aoep_pro_scenario_best") || 0)); } catch { /* */ }
  }, []);

  const current = pool[idx];

  const start = () => {
    const list = [...scenariosForTrack(track)].sort(() => Math.random() - 0.5);
    setPool(list); setIdx(0); setScore(0); setFeedback(""); setAnswered(false);
    setPhase("playing");
  };

  const pick = (optIdx: number) => {
    if (!current || answered || phase !== "playing") return;
    setAnswered(true);
    const correct = optIdx === current.answer;
    if (correct) setScore((s) => s + 1);
    setFeedback(correct
      ? `✓ Correct — ${current.explain}${current.policy ? ` (${current.policy})` : ""}`
      : `✗ Best action: "${current.options[current.answer]}". ${current.explain}`);
    setTimeout(() => {
      const next = idx + 1;
      if (next >= pool.length) {
        setPhase("done");
        const final = score + (correct ? 1 : 0);
        try {
          const b = Math.max(final, best);
          localStorage.setItem("aoep_pro_scenario_best", String(b));
          setBest(b);
        } catch { /* */ }
        return;
      }
      setIdx(next); setFeedback(""); setAnswered(false);
    }, 1800);
  };

  const pct = pool.length ? Math.round((score / pool.length) * 100) : 0;

  return (
    <main className="container" style={{ maxWidth: 760 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>💼 What Would You Do?</h1>
        <Link href="/corporate" style={{ marginLeft: "auto" }}>Corporate courses</Link>
        <Link href="/arcade">Arcade</Link>
      </div>
      <p className="muted">
        Professional scenario drills — read the situation, choose the compliant and safe action.
        Practice for corporate training assessments.
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <button onClick={() => setTrack("all")} disabled={phase === "playing"}
          style={{ opacity: track === "all" ? 1 : 0.55 }}>All tracks</button>
        {(Object.keys(TRACK_LABELS) as ProTrack[]).map((t) => (
          <button key={t} onClick={() => setTrack(t)} disabled={phase === "playing"}
            style={{ opacity: track === t ? 1 : 0.55 }}>{TRACK_LABELS[t]}</button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best streak: {best}</span>
      </div>

      {phase === "idle" && (
        <div className="card" style={{ textAlign: "center", padding: 32, borderLeft: "4px solid #6366f1" }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🎯</div>
          <p>{scenariosForTrack(track).length} scenarios · {track === "all" ? "all tracks" : TRACK_LABELS[track]}</p>
          <button onClick={start} style={{ background: "#4338ca", color: "#fff", padding: "14px 32px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
            ▶ Start scenario drill
          </button>
        </div>
      )}

      {phase === "playing" && current && (
        <div className="card" style={{ borderLeft: `4px solid ${trackColor(current.track)}` }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#94a3b8" }}>
            <span>{TRACK_LABELS[current.track]}</span>
            <span>{idx + 1} / {pool.length} · Score {score}</span>
          </div>
          <h3 style={{ marginTop: 8 }}>{current.title}</h3>
          <div style={{
            padding: "14px 16px", borderRadius: 10, background: "rgba(99,102,241,0.08)",
            border: "1px solid rgba(99,102,241,0.2)", marginBottom: 16, lineHeight: 1.6,
          }}>
            {current.setup}
          </div>
          <p style={{ fontWeight: 700, fontSize: 17 }}>{current.prompt}</p>
          <div style={{ display: "grid", gap: 10, marginTop: 16 }}>
            {current.options.map((opt, i) => (
              <button key={i} onClick={() => pick(i)} disabled={answered}
                style={{
                  textAlign: "left", padding: "14px 16px", fontSize: 15,
                  opacity: answered ? 0.7 : 1,
                  border: answered && i === current.answer ? "2px solid #34d399" : "1px solid var(--border)",
                  background: answered && i === current.answer ? "rgba(52,211,153,0.12)" : "transparent",
                }}>
                {opt}
              </button>
            ))}
          </div>
          {feedback && (
            <p style={{ marginTop: 16, color: feedback.startsWith("✓") ? "#34d399" : "#f87171", lineHeight: 1.5 }}>
              {feedback}
            </p>
          )}
        </div>
      )}

      {phase === "done" && (
        <div className="card" style={{ textAlign: "center", padding: 28 }}>
          <h2>{pct >= 80 ? "🎉 Strong judgment!" : pct >= 60 ? "📋 Good effort" : "📚 Keep practicing"}</h2>
          <p>Score: <strong>{score}</strong> / {pool.length} ({pct}%)</p>
          <p className="muted">Review corporate courses for deeper policy training.</p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 16, flexWrap: "wrap" }}>
            <button onClick={start} style={{ background: "#4338ca", color: "#fff", padding: "12px 24px", borderRadius: 8, border: 0, cursor: "pointer" }}>
              Drill again
            </button>
            <Link href="/corporate" style={{ padding: "12px 24px", borderRadius: 8, border: "1px solid var(--border)" }}>
              Browse courses
            </Link>
          </div>
        </div>
      )}
    </main>
  );
}

function trackColor(track: ProTrack): string {
  return {
    compliance: "#6366f1", safety: "#dc2626", privacy: "#0891b2",
    ethics: "#7c3aed", security: "#ea580c", trade: "#059669",
  }[track];
}

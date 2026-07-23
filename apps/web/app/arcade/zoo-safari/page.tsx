"use client";

// Zoo Safari — memorize land animal species. See emoji + clue, pick the correct
// name. Build your field guide codex as you identify each species correctly.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { type Age, type Species, ZOO_SPECIES, quizOptions } from "../../lib/speciesData";

export default function ZooSafari() {
  const [age, setAge] = useState<Age>("tween");
  const [phase, setPhase] = useState<"idle" | "playing" | "done">("idle");
  const [pool, setPool] = useState<Species[]>([]);
  const [idx, setIdx] = useState(0);
  const [codex, setCodex] = useState<Set<string>>(new Set());
  const [score, setScore] = useState(0);
  const [lives, setLives] = useState(3);
  const [feedback, setFeedback] = useState("");
  const [options, setOptions] = useState<string[]>([]);
  const [best, setBest] = useState(0);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
    try { setBest(Number(localStorage.getItem(`aoep_zoo_best_${q || "tween"}`) || 0)); } catch { /* */ }
  }, []);

  const current = pool[idx];

  const loadRound = useCallback((species: Species, all: Species[]) => {
    setOptions(quizOptions(species, all));
  }, []);

  const start = () => {
    const list = [...ZOO_SPECIES[age]].sort(() => Math.random() - 0.5);
    setPool(list); setIdx(0); setCodex(new Set()); setScore(0); setLives(3);
    setFeedback(""); setPhase("playing");
    loadRound(list[0], list);
  };

  useEffect(() => {
    if (phase === "playing" && current) loadRound(current, pool);
  }, [idx, phase, current, pool, loadRound]);

  const answer = (name: string) => {
    if (!current || phase !== "playing") return;
    const correct = name === current.name;
    if (correct) {
      setScore((s) => s + 1);
      setCodex((c) => new Set(c).add(current.id));
      setFeedback(`✓ ${current.name} — ${current.habitat}${current.scientific ? ` (${current.scientific})` : ""}`);
    } else {
      setLives((l) => l - 1);
      setFeedback(`✗ That was ${current.name}. ${current.clue}`);
    }
    setTimeout(() => {
      if (!correct && lives - 1 <= 0) {
        setPhase("done");
        try {
          const b = Math.max(score + (correct ? 1 : 0), best);
          localStorage.setItem(`aoep_zoo_best_${age}`, String(b));
          setBest(b);
        } catch { /* */ }
        return;
      }
      const next = idx + 1;
      if (next >= pool.length) {
        setPhase("done");
        const final = score + (correct ? 1 : 0);
        try {
          const b = Math.max(final, best);
          localStorage.setItem(`aoep_zoo_best_${age}`, String(b));
          setBest(b);
        } catch { /* */ }
        return;
      }
      setIdx(next);
      setFeedback("");
    }, 1200);
  };

  return (
    <main className="container" style={{ maxWidth: 720 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🦁 Zoo Safari</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/arcade/species-match">🃏 Species Match</Link>
      </div>
      <p className="muted">Memorize animal species — read the clue, identify the animal, and fill your field guide codex.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={phase === "playing"}
            style={{ opacity: age === a ? 1 : 0.55 }}>{a}</button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best: {best}</span>
      </div>

      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 32 }}>
          <div style={{ fontSize: 64, marginBottom: 16 }}>🦒🐘🦜</div>
          <button onClick={start} style={{ background: "#b45309", color: "#fff", padding: "14px 32px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
            ▶ Start Safari
          </button>
        </div>
      )}

      {phase === "playing" && current && (
        <div className="card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: 13, color: "#94a3b8" }}>
            Species {idx + 1} / {pool.length} · ♥ {lives} · Score {score}
          </div>
          <div style={{ fontSize: 96, margin: "16px 0" }}>{current.emoji}</div>
          <p style={{ fontSize: 18, fontWeight: 600 }}>{current.clue}</p>
          <p className="muted">{current.habitat}</p>
          <div style={{ display: "grid", gap: 10, marginTop: 20, maxWidth: 400, margin: "20px auto 0" }}>
            {options.map((opt) => (
              <button key={opt} onClick={() => answer(opt)} style={{ padding: "12px 16px", fontSize: 16, textAlign: "left" }}>
                {opt}
              </button>
            ))}
          </div>
          {feedback && <p style={{ marginTop: 16, color: feedback.startsWith("✓") ? "#34d399" : "#f87171" }}>{feedback}</p>}
          <div style={{ marginTop: 20, display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center" }}>
            {pool.map((s) => (
              <span key={s.id} title={s.name} style={{
                fontSize: 24, opacity: codex.has(s.id) ? 1 : 0.25,
                filter: codex.has(s.id) ? "none" : "grayscale(1)",
              }}>{s.emoji}</span>
            ))}
          </div>
        </div>
      )}

      {phase === "done" && (
        <div className="card" style={{ textAlign: "center", padding: 24 }}>
          <h2>{codex.size === pool.length ? "🎉 Codex complete!" : "Safari over"}</h2>
          <p>Identified <strong>{codex.size}</strong> / {pool.length} species · Score {score}</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", margin: "16px 0" }}>
            {pool.filter((s) => codex.has(s.id)).map((s) => (
              <span key={s.id} style={{ background: "#1e293b", padding: "6px 12px", borderRadius: 8 }}>
                {s.emoji} {s.name}
              </span>
            ))}
          </div>
          <button onClick={start} style={{ background: "#b45309", color: "#fff", padding: "12px 28px", borderRadius: 10, border: 0, cursor: "pointer" }}>
            Safari again
          </button>
        </div>
      )}
    </main>
  );
}

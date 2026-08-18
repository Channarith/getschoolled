"use client";

// Reef Quest — memorize fish & marine species. Identify creatures from emoji,
// habitat, and clues. Fill your reef journal as you learn each species.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { type Age, type Species, REEF_SPECIES, quizOptions } from "../../lib/speciesData";

export default function ReefQuest() {
  const [age, setAge] = useState<Age>("tween");
  const [phase, setPhase] = useState<"idle" | "playing" | "done">("idle");
  const [pool, setPool] = useState<Species[]>([]);
  const [idx, setIdx] = useState(0);
  const [journal, setJournal] = useState<Set<string>>(new Set());
  const [score, setScore] = useState(0);
  const [lives, setLives] = useState(3);
  const [feedback, setFeedback] = useState("");
  const [options, setOptions] = useState<string[]>([]);
  const [best, setBest] = useState(0);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  // Reload the best score whenever the age group changes — reading it once at
  // mount meant an in-page age switch compared/saved against the WRONG age's best.
  useEffect(() => {
    try { setBest(Number(localStorage.getItem(`aoep_reef_best_${age}`) || 0)); } catch { /* */ }
  }, [age]);

  const current = pool[idx];

  const loadRound = useCallback((species: Species, all: Species[]) => {
    setOptions(quizOptions(species, all));
  }, []);

  const start = () => {
    const list = [...REEF_SPECIES[age]].sort(() => Math.random() - 0.5);
    setPool(list); setIdx(0); setJournal(new Set()); setScore(0); setLives(3);
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
      setJournal((j) => new Set(j).add(current.id));
      setFeedback(`✓ ${current.name} — ${current.group}${current.scientific ? ` · ${current.scientific}` : ""}`);
    } else {
      setLives((l) => l - 1);
      setFeedback(`✗ That was ${current.name}. ${current.clue}`);
    }
    setTimeout(() => {
      if (!correct && lives - 1 <= 0) {
        setPhase("done");
        // Running out of lives is the common exit — still record the best.
        const final = score;
        try {
          const b = Math.max(final, best);
          localStorage.setItem(`aoep_reef_best_${age}`, String(b));
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
          localStorage.setItem(`aoep_reef_best_${age}`, String(b));
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
        <h1 style={{ margin: 0 }}>🐠 Reef Quest</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/arcade/zoo-safari">🦁 Zoo Safari</Link>
      </div>
      <p className="muted">Memorize fish and marine species — identify each creature and log it in your reef journal.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={phase === "playing"}
            style={{ opacity: age === a ? 1 : 0.55 }}>{a}</button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best: {best}</span>
      </div>

      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 32, background: "linear-gradient(180deg, #0c4a6e, #164e63)", borderRadius: 16 }}>
          <div style={{ fontSize: 64, marginBottom: 16 }}>🐡🦈🐙</div>
          <button onClick={start} style={{ background: "#0891b2", color: "#fff", padding: "14px 32px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
            ▶ Dive in
          </button>
        </div>
      )}

      {phase === "playing" && current && (
        <div className="card" style={{ textAlign: "center", borderColor: "#0891b2" }}>
          <div style={{ fontSize: 13, color: "#94a3b8" }}>
            Species {idx + 1} / {pool.length} · ♥ {lives} · Score {score}
          </div>
          <div style={{ fontSize: 96, margin: "16px 0" }}>{current.emoji}</div>
          <p style={{ fontSize: 18, fontWeight: 600 }}>{current.clue}</p>
          <p className="muted">📍 {current.habitat}</p>
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
                fontSize: 24, opacity: journal.has(s.id) ? 1 : 0.25,
              }}>{s.emoji}</span>
            ))}
          </div>
        </div>
      )}

      {phase === "done" && (
        <div className="card" style={{ textAlign: "center", padding: 24 }}>
          <h2>{journal.size === pool.length ? "🎉 Reef journal complete!" : "Dive complete"}</h2>
          <p>Logged <strong>{journal.size}</strong> / {pool.length} species · Score {score}</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", margin: "16px 0" }}>
            {pool.filter((s) => journal.has(s.id)).map((s) => (
              <span key={s.id} style={{ background: "#0c4a6e", padding: "6px 12px", borderRadius: 8 }}>
                {s.emoji} {s.name}
              </span>
            ))}
          </div>
          <button onClick={start} style={{ background: "#0891b2", color: "#fff", padding: "12px 28px", borderRadius: 10, border: 0, cursor: "pointer" }}>
            Dive again
          </button>
        </div>
      )}
    </main>
  );
}

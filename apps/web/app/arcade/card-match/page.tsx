"use client";

// Card Match — Educational memory matching game (Solitaire-inspired).
// Flip pairs to match TERM cards with DEFINITION cards.
// Age-scaled content. Beat your best time!

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Pair = { term: string; def: string };
type Card = { id: string; face: string; type: "term" | "def"; pairIdx: number; flipped: boolean; matched: boolean };

const PAIRS: Record<Age, Pair[]> = {
  kids: [
    { term: "🐱 Cat", def: "Meows" }, { term: "🐶 Dog", def: "Barks" },
    { term: "🐄 Cow", def: "Moos" }, { term: "🐸 Frog", def: "Croaks" },
    { term: "🌞 Sun", def: "Gives light" }, { term: "🌧️ Rain", def: "Water from clouds" },
    { term: "2 + 2", def: "4" }, { term: "5 × 2", def: "10" },
  ],
  tween: [
    { term: "Photosynthesis", def: "Plants make food from sunlight" },
    { term: "Gravity", def: "Force that pulls objects down" },
    { term: "Metaphor", def: "Comparison without 'like' or 'as'" },
    { term: "Denominator", def: "Bottom number of a fraction" },
    { term: "Synonym", def: "Word with the same meaning" },
    { term: "Ecosystem", def: "Community of living things + environment" },
    { term: "Continent", def: "Large landmass (7 total on Earth)" },
    { term: "Evaporation", def: "Liquid turning into gas" },
  ],
  teen: [
    { term: "Mitosis", def: "Cell division producing 2 identical cells" },
    { term: "Alliteration", def: "Repeated consonant sounds at word starts" },
    { term: "f(x) = x²", def: "Parabola opening upward" },
    { term: "Oxidation", def: "Loss of electrons in a reaction" },
    { term: "Irony", def: "Opposite of what is expected" },
    { term: "Momentum", def: "Mass × velocity" },
    { term: "Democracy", def: "Government by the people" },
    { term: "Pythagorean theorem", def: "a² + b² = c²" },
  ],
  adult: [
    { term: "Entropy", def: "Measure of disorder in a system" },
    { term: "Dialectic", def: "Resolution of opposing ideas through reasoning" },
    { term: "Regression to mean", def: "Extreme outcomes trend toward average over time" },
    { term: "Cognitive dissonance", def: "Discomfort from conflicting beliefs" },
    { term: "Opportunity cost", def: "Value of the next best alternative forgone" },
    { term: "Bayesian inference", def: "Updating beliefs with new evidence" },
    { term: "Hegemony", def: "Dominance of one entity over others" },
    { term: "Half-life", def: "Time for half of a substance to decay" },
  ],
};

function buildDeck(pairs: Pair[]): Card[] {
  const deck: Card[] = [];
  pairs.forEach((p, i) => {
    deck.push({ id: `t${i}`, face: p.term, type: "term", pairIdx: i, flipped: false, matched: false });
    deck.push({ id: `d${i}`, face: p.def, type: "def", pairIdx: i, flipped: false, matched: false });
  });
  return deck.sort(() => Math.random() - 0.5);
}

export default function CardMatch() {
  const [age, setAge] = useState<Age>("tween");
  const [deck, setDeck] = useState<Card[]>(() => buildDeck(PAIRS.tween));
  const [selected, setSelected] = useState<string[]>([]);
  const [score, setScore] = useState(0);
  const [misses, setMisses] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [best, setBest] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") {
      setAge(q as Age); setDeck(buildDeck(PAIRS[q as Age]));
    }
    try { const b = localStorage.getItem(`aoep_cardmatch_best_${q || "tween"}`); if (b) setBest(Number(b)); } catch { /* */ }
  }, []);

  function start() {
    setDeck(buildDeck(PAIRS[age]));
    setSelected([]); setScore(0); setMisses(0); setElapsed(0); setDone(false);
    if (timerRef.current) clearInterval(timerRef.current);
    setRunning(true);
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
  }

  useEffect(() => { if (!running) return; return () => { if (timerRef.current) clearInterval(timerRef.current); }; }, [running]);

  function flip(id: string) {
    if (!running || done) return;
    const card = deck.find((c) => c.id === id);
    if (!card || card.flipped || card.matched || selected.length >= 2) return;

    const newSel = [...selected, id];
    const newDeck = deck.map((c) => c.id === id ? { ...c, flipped: true } : c);
    setDeck(newDeck);
    setSelected(newSel);

    if (newSel.length === 2) {
      const [a, b] = newSel.map((sid) => newDeck.find((c) => c.id === sid)!);
      if (a.pairIdx === b.pairIdx && a.type !== b.type) {
        // Match!
        setTimeout(() => {
          setDeck((d) => d.map((c) => newSel.includes(c.id) ? { ...c, matched: true } : c));
          setScore((s) => s + 10);
          setSelected([]);
          const remaining = newDeck.filter((c) => !c.matched && !newSel.includes(c.id));
          if (remaining.length === 0) {
            setDone(true); setRunning(false);
            if (timerRef.current) clearInterval(timerRef.current);
            const key = `aoep_cardmatch_best_${age}`;
            try {
              const prev = Number(localStorage.getItem(key) || "9999");
              if (elapsed < prev || prev === 9999) { localStorage.setItem(key, String(elapsed)); setBest(elapsed); }
            } catch { /* */ }
          }
        }, 300);
      } else {
        setTimeout(() => {
          setDeck((d) => d.map((c) => newSel.includes(c.id) ? { ...c, flipped: false } : c));
          setMisses((m) => m + 1);
          setSelected([]);
        }, 900);
      }
    }
  }

  const matched = deck.filter((c) => c.matched).length / 2;
  const total = deck.length / 2;

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
        <h1 style={{ margin: 0 }}>🃏 Card Match</h1>
        <Link href="/arcade" style={{ marginLeft: "auto", color: "#94a3b8" }}>← Arcade</Link>
      </div>
      <p className="muted">Flip pairs to match terms with their definitions. Beat your best time!</p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => { setAge(a); setDeck(buildDeck(PAIRS[a])); setSelected([]); setDone(false); setRunning(false); setElapsed(0); }}
            disabled={running} style={{ opacity: age === a ? 1 : 0.5, fontWeight: age === a ? 700 : 400 }}>{a}</button>
        ))}
        <button onClick={start} style={{ marginLeft: "auto", background: "#0f766e", color: "#fff", padding: "8px 18px", fontWeight: 700 }}>
          {running || done ? "↺ Restart" : "▶ Start"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 20, marginBottom: 12, fontSize: 14, color: "#94a3b8" }}>
        <span>✅ {matched}/{total}</span>
        <span>⏱ {elapsed}s</span>
        <span>❌ {misses} misses</span>
        {best && <span>🏆 Best: {best}s</span>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
        {deck.map((card) => (
          <button key={card.id} onClick={() => flip(card.id)}
            disabled={card.matched || card.flipped || selected.length >= 2}
            style={{
              minHeight: 70, padding: 8, borderRadius: 10, fontSize: 12, fontWeight: 600,
              cursor: card.matched ? "default" : "pointer",
              background: card.matched ? "#14532d" : card.flipped ? (card.type === "term" ? "#312e81" : "#164e63") : "#1e293b",
              color: card.matched ? "#86efac" : card.flipped ? "#e2e8f0" : "#475569",
              border: `2px solid ${card.matched ? "#16a34a" : card.flipped ? (card.type === "term" ? "#818cf8" : "#22d3ee") : "#334155"}`,
              transition: "all 0.2s",
              textAlign: "center",
            }}>
            {card.flipped || card.matched ? card.face : "?"}
          </button>
        ))}
      </div>

      {done && (
        <div style={{ textAlign: "center", padding: 24, marginTop: 16 }}>
          <div style={{ fontSize: 48 }}>🎉</div>
          <h2>Matched all {total} pairs in {elapsed}s!</h2>
          <div style={{ color: "#94a3b8" }}>{misses} misses · Score: {score} pts{best === elapsed ? " · 🏆 New best!" : ""}</div>
          <button onClick={start} style={{ marginTop: 12, background: "#0f766e", color: "#fff",
            padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer", fontWeight: 700 }}>
            ▶ Play again
          </button>
        </div>
      )}
    </main>
  );
}

"use client";

// Species Match — memory game to memorize zoo animals and reef fish.
// Flip cards to match species emoji+name with habitat clues.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { type Age, type Species, ZOO_SPECIES, REEF_SPECIES } from "../../lib/speciesData";

type Mode = "zoo" | "reef" | "mixed";
type Card = { id: string; face: string; sub: string; pairId: string; flipped: boolean; matched: boolean };

function buildDeck(species: Species[]): Card[] {
  const deck: Card[] = [];
  species.forEach((s) => {
    deck.push({
      id: `n-${s.id}`, face: `${s.emoji} ${s.name}`, sub: s.group,
      pairId: s.id, flipped: false, matched: false,
    });
    deck.push({
      id: `h-${s.id}`, face: s.habitat, sub: s.clue.slice(0, 40) + (s.clue.length > 40 ? "…" : ""),
      pairId: s.id, flipped: false, matched: false,
    });
  });
  return deck.sort(() => Math.random() - 0.5);
}

function pickSpecies(age: Age, mode: Mode): Species[] {
  const zoo = ZOO_SPECIES[age].slice(0, 6);
  const reef = REEF_SPECIES[age].slice(0, 6);
  if (mode === "zoo") return zoo;
  if (mode === "reef") return reef;
  return [...zoo.slice(0, 4), ...reef.slice(0, 4)];
}

export default function SpeciesMatch() {
  const [age, setAge] = useState<Age>("tween");
  const [mode, setMode] = useState<Mode>("mixed");
  const [deck, setDeck] = useState<Card[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [matched, setMatched] = useState(0);
  const [misses, setMisses] = useState(0);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const checking = useRef(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const a = q.get("age");
    if (a === "kids" || a === "tween" || a === "teen" || a === "adult") setAge(a);
    const m = q.get("mode");
    if (m === "zoo" || m === "reef" || m === "mixed") setMode(m);
  }, []);

  const totalPairs = pickSpecies(age, mode).length;

  function start() {
    const species = pickSpecies(age, mode);
    setDeck(buildDeck(species));
    setSelected([]); setMatched(0); setMisses(0); setElapsed(0); setDone(false);
    checking.current = false;
    setRunning(true);
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(() => setElapsed((e) => e + 1), 1000);
  }

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  function flip(id: string) {
    if (!running || done || checking.current) return;
    const card = deck.find((c) => c.id === id);
    if (!card || card.flipped || card.matched) return;
    if (selected.length >= 2) return;

    const nextSel = [...selected, id];
    const nextDeck = deck.map((c) => (c.id === id ? { ...c, flipped: true } : c));
    setDeck(nextDeck);
    setSelected(nextSel);

    if (nextSel.length < 2) return;

    checking.current = true;
    const [a, b] = nextSel.map((sid) => nextDeck.find((c) => c.id === sid)!);
    const isMatch = a.pairId === b.pairId;

    setTimeout(() => {
      if (isMatch) {
        const updated = nextDeck.map((c) =>
          c.pairId === a.pairId ? { ...c, matched: true, flipped: true } : c,
        );
        setDeck(updated);
        const newMatched = matched + 1;
        setMatched(newMatched);
        if (newMatched >= totalPairs) {
          setDone(true); setRunning(false);
          if (timer.current) clearInterval(timer.current);
        }
      } else {
        setDeck(nextDeck.map((c) =>
          nextSel.includes(c.id) ? { ...c, flipped: false } : c,
        ));
        setMisses((m) => m + 1);
      }
      setSelected([]);
      checking.current = false;
    }, 700);
  }

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🃏 Species Match</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted">Memory match — pair each species with its habitat to memorize zoo animals and reef fish.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55 }}>{a}</button>
        ))}
        <span className="muted" style={{ margin: "0 8px" }}>|</span>
        {(["zoo", "reef", "mixed"] as Mode[]).map((m) => (
          <button key={m} onClick={() => setMode(m)} disabled={running}
            style={{ opacity: mode === m ? 1 : 0.55, textTransform: "capitalize" }}>{m}</button>
        ))}
      </div>

      {!running && !done && (
        <div style={{ textAlign: "center", padding: 24 }}>
          <button onClick={start} style={{ background: "#059669", color: "#fff", padding: "14px 32px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
            ▶ {totalPairs} pairs · Play
          </button>
        </div>
      )}

      {(running || done) && (
        <>
          <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 14 }}>
            <span>Matched: {matched}/{totalPairs}</span>
            <span>Misses: {misses}</span>
            <span>Time: {elapsed}s</span>
          </div>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: 10,
          }}>
            {deck.map((c) => (
              <button key={c.id} onClick={() => flip(c.id)}
                disabled={c.matched || (c.flipped && selected.length >= 2)}
                style={{
                  minHeight: 100, padding: 12, borderRadius: 10,
                  background: c.matched ? "rgba(52,211,153,0.2)" : c.flipped ? "#1e3a5f" : "#0f172a",
                  border: `2px solid ${c.matched ? "#34d399" : c.flipped ? "#38bdf8" : "#334155"}`,
                  color: "#e2e8f0", cursor: c.matched ? "default" : "pointer",
                  fontSize: c.face.length > 20 ? 13 : 15, fontWeight: 600,
                  opacity: c.matched ? 0.7 : 1,
                }}>
                {c.flipped || c.matched ? (
                  <>
                    <div>{c.face}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4, fontWeight: 400 }}>{c.sub}</div>
                  </>
                ) : "?"}
              </button>
            ))}
          </div>
          {done && (
            <div className="card" style={{ textAlign: "center", marginTop: 20 }}>
              <h2>🎉 All species matched!</h2>
              <p>{elapsed}s · {misses} misses</p>
              <button onClick={start} style={{ background: "#059669", color: "#fff", padding: "10px 24px", borderRadius: 8, border: 0, cursor: "pointer" }}>
                Play again
              </button>
            </div>
          )}
        </>
      )}

      <div style={{ marginTop: 24, display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Link href="/arcade/zoo-safari" className="card" style={{ flex: 1, minWidth: 200, textDecoration: "none", color: "inherit" }}>
          <strong>🦁 Zoo Safari</strong>
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>Identify land animals</p>
        </Link>
        <Link href="/arcade/reef-quest" className="card" style={{ flex: 1, minWidth: 200, textDecoration: "none", color: "inherit" }}>
          <strong>🐠 Reef Quest</strong>
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>Identify fish & marine life</p>
        </Link>
      </div>
    </main>
  );
}

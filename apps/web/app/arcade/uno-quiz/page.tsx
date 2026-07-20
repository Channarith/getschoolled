"use client";

// Uno Quiz — Uno-inspired card game with educational twists.
// Play cards matching color OR number. Special cards require answering a question.
// First to empty hand wins. Says "UNO!" automatically on last card.

import Link from "next/link";
import { useEffect, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Color = "red" | "blue" | "green" | "yellow";
type CardType = "number" | "skip" | "reverse" | "draw2" | "wild";
type UnoCard = { id: string; color: Color | "wild"; value: number | string; type: CardType };
type Q = { prompt: string; options: string[]; answer: number };

const COLORS: Color[] = ["red", "blue", "green", "yellow"];
const COLOR_BG: Record<string, string> = {
  red: "#dc2626", blue: "#2563eb", green: "#16a34a", yellow: "#ca8a04", wild: "#7c3aed"
};

const QUESTIONS: Record<Age, Q[]> = {
  kids: [
    { prompt: "3 + 4 = ?", options: ["5","6","7","8"], answer: 2 },
    { prompt: "What color is the sky?", options: ["Green","Blue","Red","Pink"], answer: 1 },
    { prompt: "How many legs does a cat have?", options: ["2","4","6","8"], answer: 1 },
    { prompt: "5 × 2 = ?", options: ["8","9","10","11"], answer: 2 },
    { prompt: "Which is biggest?", options: ["Ant","Dog","Elephant","Cat"], answer: 2 },
    { prompt: "10 − 3 = ?", options: ["6","7","8","9"], answer: 1 },
  ],
  tween: [
    { prompt: "7 × 8 = ?", options: ["54","56","58","64"], answer: 1 },
    { prompt: "Capital of France?", options: ["London","Berlin","Paris","Rome"], answer: 2 },
    { prompt: "H₂O is…", options: ["Salt","Water","Air","Sugar"], answer: 1 },
    { prompt: "√64 = ?", options: ["6","7","8","9"], answer: 2 },
    { prompt: "Largest planet?", options: ["Earth","Saturn","Jupiter","Venus"], answer: 2 },
    { prompt: "12 × 12 = ?", options: ["132","140","144","148"], answer: 2 },
  ],
  teen: [
    { prompt: "Solve: 2x = 14, x = ?", options: ["5","6","7","8"], answer: 2 },
    { prompt: "DNA is found in…", options: ["Mitochondria","Nucleus","Ribosome","Cytoplasm"], answer: 1 },
    { prompt: "Shakespeare wrote…", options: ["Don Quixote","Hamlet","Odyssey","Faust"], answer: 1 },
    { prompt: "Speed of light ≈", options: ["3×10⁴ m/s","3×10⁶ m/s","3×10⁸ m/s","3×10¹⁰ m/s"], answer: 2 },
    { prompt: "Area of circle r=3? (π≈3.14)", options: ["9.42","18.84","28.26","37.68"], answer: 2 },
    { prompt: "pH below 7 is…", options: ["Neutral","Basic","Acidic","Alkaline"], answer: 2 },
  ],
  adult: [
    { prompt: "GDP measures…", options: ["Population","Trade","Economic output","Debt"], answer: 2 },
    { prompt: "E = mc²: c is…", options: ["Constant","Speed of light","Charge","Celsius"], answer: 1 },
    { prompt: "'I think therefore I am' — who said it?", options: ["Kant","Plato","Descartes","Hegel"], answer: 2 },
    { prompt: "Big-O of binary search?", options: ["O(n)","O(log n)","O(n²)","O(1)"], answer: 1 },
    { prompt: "∫2x dx = ?", options: ["x","x²+C","2x²","2"], answer: 1 },
    { prompt: "Heisenberg uncertainty involves position and…", options: ["Energy","Momentum","Mass","Velocity"], answer: 1 },
  ],
};

let _id = 0;
function mkCard(color: Color | "wild", value: number | string, type: CardType): UnoCard {
  return { id: `c${_id++}`, color, value, type };
}

function buildDeck(): UnoCard[] {
  const deck: UnoCard[] = [];
  COLORS.forEach((c) => {
    for (let n = 0; n <= 9; n++) deck.push(mkCard(c, n, "number"));
    deck.push(mkCard(c, "⛔", "skip"));
    deck.push(mkCard(c, "↩", "reverse"));
    deck.push(mkCard(c, "+2", "draw2"));
  });
  for (let i = 0; i < 4; i++) deck.push(mkCard("wild", "🌈", "wild"));
  return deck.sort(() => Math.random() - 0.5);
}

function canPlay(card: UnoCard, top: UnoCard): boolean {
  if (card.type === "wild") return true;
  return card.color === top.color || card.value === top.value;
}

function randomQ(age: Age, used: Set<number>): { q: Q; idx: number } {
  const bank = QUESTIONS[age];
  const avail = bank.map((_, i) => i).filter((i) => !used.has(i));
  const pool = avail.length ? avail : bank.map((_, i) => i);
  const idx = pool[Math.floor(Math.random() * pool.length)];
  return { q: bank[idx], idx };
}

export default function UnoQuiz() {
  const [age, setAge] = useState<Age>("tween");
  const [phase, setPhase] = useState<"idle" | "playing" | "question" | "done">("idle");
  const [deck, setDeck] = useState<UnoCard[]>([]);
  const [playerHand, setPlayerHand] = useState<UnoCard[]>([]);
  const [aiHand, setAiHand] = useState<UnoCard[]>([]);
  const [discard, setDiscard] = useState<UnoCard[]>([]);
  const [turn, setTurn] = useState<"player" | "ai">("player");
  const [winner, setWinner] = useState<"player" | "ai" | null>(null);
  const [pendingCard, setPendingCard] = useState<UnoCard | null>(null);
  const [question, setQuestion] = useState<Q | null>(null);
  const [usedQ, setUsedQ] = useState(new Set<number>());
  const [msg, setMsg] = useState("");
  const [wildColor, setWildColor] = useState<Color>("red");
  const [pickingColor, setPickingColor] = useState(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q as Age);
  }, []);

  function deal() {
    const d = buildDeck();
    const ph = d.splice(0, 7);
    const ah = d.splice(0, 7);
    // Make sure top card is a number
    let top = d.splice(0, 1)[0];
    while (top.type !== "number") { d.push(top); top = d.splice(0, 1)[0]; }
    setDeck(d); setPlayerHand(ph); setAiHand(ah); setDiscard([top]);
    setTurn("player"); setWinner(null); setPendingCard(null);
    setQuestion(null); setUsedQ(new Set()); setMsg("");
    setPhase("playing");
  }

  const topCard = discard[discard.length - 1];
  const effectiveTop = topCard ? (pickingColor ? { ...topCard, color: wildColor } : topCard) : null;

  function applyCard(card: UnoCard, hand: "player" | "ai", targetHand: UnoCard[], color?: Color): { newHand: UnoCard[]; newDeck: UnoCard[]; newAiHand: UnoCard[] } {
    let d = [...deck];
    let ph = hand === "player" ? targetHand.filter((c) => c.id !== card.id) : [...playerHand];
    let ah = hand === "ai" ? targetHand.filter((c) => c.id !== card.id) : [...aiHand];
    const draw = (target: "player" | "ai", n: number) => {
      for (let i = 0; i < n; i++) {
        if (!d.length) { d = discard.slice(0, -1).sort(() => Math.random() - 0.5); }
        const drawn = d.splice(0, 1)[0];
        if (drawn) { if (target === "player") ph.push(drawn); else ah.push(drawn); }
      }
    };
    if (card.type === "draw2") { const opp = hand === "player" ? "ai" : "player"; draw(opp, 2); }
    if (card.type === "wild" && color) { }
    return { newHand: hand === "player" ? ph : ah, newDeck: d, newAiHand: ah };
  }

  function playCard(card: UnoCard) {
    if (turn !== "player" || phase !== "playing" || !effectiveTop) return;
    if (!canPlay(card, effectiveTop)) { setMsg("❌ That card can't be played here."); return; }
    setMsg("");
    if (card.type === "wild") { setPendingCard(card); setPickingColor(true); return; }
    if (card.type !== "number") {
      const { q, idx } = randomQ(age, usedQ);
      setUsedQ((u) => new Set(u).add(idx));
      setPendingCard(card); setQuestion(q); setPhase("question");
      return;
    }
    commitPlay(card, "player", undefined);
  }

  function commitPlay(card: UnoCard, who: "player" | "ai", color?: Color) {
    const hand = who === "player" ? playerHand : aiHand;
    const { newHand, newDeck, newAiHand } = applyCard(card, who, hand, color);
    const finalCard = color ? { ...card, color } : card;
    setDiscard((d) => [...d, finalCard]);
    setDeck(newDeck);
    if (who === "player") {
      setPlayerHand(newHand);
      setAiHand(newAiHand);
      if (newHand.length === 0) { setWinner("player"); setPhase("done"); return; }
      if (card.type === "reverse" || card.type === "skip") {
        setMsg("⛔ AI skipped!"); setTurn("player");
      } else {
        setTurn("ai");
        setTimeout(() => aiTurn(newAiHand, [...discard, finalCard], newDeck), 1000);
      }
    } else {
      setAiHand(newHand);
      if (newHand.length === 0) { setWinner("ai"); setPhase("done"); return; }
      if (card.type === "reverse" || card.type === "skip") {
        setMsg("⛔ You were skipped!"); setTurn("ai");
        setTimeout(() => aiTurn(newHand, [...discard, finalCard], newDeck), 1000);
      } else {
        setTurn("player");
      }
    }
  }

  function pickColor(c: Color) {
    setPickingColor(false); setWildColor(c);
    if (pendingCard) { commitPlay(pendingCard, "player", c); setPendingCard(null); }
  }

  function answerQ(idx: number) {
    if (!question || !pendingCard) return;
    if (idx === question.answer) {
      setQuestion(null); setPhase("playing");
      commitPlay(pendingCard, "player", undefined);
      setPendingCard(null);
    } else {
      setMsg("❌ Wrong! Card goes back to hand."); setQuestion(null); setPhase("playing");
      setPendingCard(null);
    }
  }

  function drawCard() {
    if (turn !== "player" || !deck.length) return;
    const drawn = deck[0];
    setDeck(deck.slice(1));
    setPlayerHand((h) => [...h, drawn]);
    setMsg(`Drew ${drawn.color} ${drawn.value}`);
    setTurn("ai");
    setTimeout(() => aiTurn(aiHand, discard, deck.slice(1)), 800);
  }

  function aiTurn(ah: UnoCard[], disc: UnoCard[], d: UnoCard[]) {
    const top = disc[disc.length - 1];
    const playable = ah.filter((c) => canPlay(c, top));
    if (playable.length) {
      const card = playable[Math.floor(Math.random() * playable.length)];
      const color: Color = COLORS[Math.floor(Math.random() * 4)];
      const newAh = ah.filter((c) => c.id !== card.id);
      const newDisc = [...disc, card.type === "wild" ? { ...card, color } : card];
      setAiHand(newAh); setDiscard(newDisc); setDeck(d);
      setMsg(`AI played ${card.color} ${card.value}`);
      if (newAh.length === 0) { setWinner("ai"); setPhase("done"); return; }
      if (newAh.length === 1) setMsg("🤖 UNO!");
      if (card.type === "skip" || card.type === "reverse") {
        setTimeout(() => aiTurn(newAh, newDisc, d), 800);
      } else if (card.type === "draw2") {
        const drawn = d.slice(0, 2);
        setPlayerHand((h) => [...h, ...drawn]); setDeck(d.slice(2));
        setMsg("AI played +2 — you draw 2!"); setTurn("player");
      } else {
        setTurn("player");
      }
    } else {
      const drawn = d[0]; const nd = d.slice(1);
      if (drawn) { setAiHand([...ah, drawn]); setDeck(nd); setMsg("AI drew a card."); }
      setTurn("player");
    }
  }

  return (
    <main style={{ maxWidth: 680, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
        <h1 style={{ margin: 0 }}>🎴 Uno Quiz</h1>
        <Link href="/arcade" style={{ marginLeft: "auto", color: "#94a3b8" }}>← Arcade</Link>
      </div>
      <p className="muted">Play cards matching color or number. Special cards need a correct answer to activate. First to empty hand wins!</p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={phase === "playing"}
            style={{ opacity: age === a ? 1 : 0.5, fontWeight: age === a ? 700 : 400 }}>{a}</button>
        ))}
        <button onClick={deal} style={{ marginLeft: "auto", background: "#dc2626", color: "#fff", padding: "8px 18px", fontWeight: 700 }}>
          {phase !== "idle" ? "↺ New game" : "▶ Deal"}
        </button>
      </div>

      {msg && <div style={{ padding: "8px 12px", background: "#1e293b", borderRadius: 8, marginBottom: 8, color: "#cbd5e1", fontSize: 14 }}>{msg}</div>}

      {phase !== "idle" && phase !== "done" && (
        <>
          {/* AI hand */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 4 }}>🤖 AI hand ({aiHand.length} cards){aiHand.length === 1 ? " · UNO!" : ""}</div>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {aiHand.map((c) => <div key={c.id} style={{ width: 32, height: 48, borderRadius: 6, background: "#1e293b", border: "2px solid #334155" }} />)}
            </div>
          </div>

          {/* Discard + draw */}
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 16 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 11, color: "#64748b" }}>Discard</div>
              {topCard && (
                <div style={{ width: 56, height: 80, borderRadius: 10, background: COLOR_BG[topCard.color] || COLOR_BG.wild,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 20, fontWeight: 800, color: "#fff", border: "3px solid rgba(255,255,255,0.5)" }}>
                  {String(topCard.value)}
                </div>
              )}
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 11, color: "#64748b" }}>Draw ({deck.length})</div>
              <button onClick={drawCard} disabled={turn !== "player" || phase !== "playing"}
                style={{ width: 56, height: 80, borderRadius: 10, background: "#1e293b", border: "2px dashed #4b5563",
                  cursor: turn === "player" && phase === "playing" ? "pointer" : "default", fontSize: 22 }}>
                🂠
              </button>
            </div>
            <div style={{ color: turn === "player" ? "#4ade80" : "#fbbf24", fontWeight: 700, fontSize: 13 }}>
              {turn === "player" ? "Your turn" : "AI thinking…"}
            </div>
          </div>

          {/* Wild color picker */}
          {pickingColor && (
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <span style={{ color: "#94a3b8", alignSelf: "center", fontSize: 13 }}>Pick a color:</span>
              {COLORS.map((c) => (
                <button key={c} onClick={() => pickColor(c)}
                  style={{ width: 44, height: 44, borderRadius: 10, background: COLOR_BG[c], border: "none", cursor: "pointer" }} />
              ))}
            </div>
          )}

          {/* Question overlay */}
          {phase === "question" && question && (
            <div style={{ padding: 16, background: "#0f172a", borderRadius: 12, border: "2px solid #fbbf24", marginBottom: 12 }}>
              <div style={{ fontWeight: 700, color: "#fbbf24", marginBottom: 10 }}>Answer to play that special card: {question.prompt}</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {question.options.map((opt, i) => (
                  <button key={i} onClick={() => answerQ(i)}
                    style={{ padding: "10px", borderRadius: 8, background: "#1e293b", color: "#e2e8f0", fontWeight: 600, cursor: "pointer" }}>
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Player hand */}
          <div>
            <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 6 }}>
              Your hand ({playerHand.length}){playerHand.length === 1 ? " · 🎴 UNO!" : ""}
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {playerHand.map((card) => {
                const playable = effectiveTop && canPlay(card, effectiveTop) && turn === "player" && phase === "playing";
                return (
                  <button key={card.id} onClick={() => playCard(card)} disabled={!playable}
                    title={playable ? "Play this card" : "Can't play yet"}
                    style={{
                      width: 52, height: 76, borderRadius: 10, border: `3px solid ${playable ? "#fff" : "transparent"}`,
                      background: COLOR_BG[card.color] || COLOR_BG.wild,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 16, fontWeight: 800, color: "#fff",
                      cursor: playable ? "pointer" : "default",
                      opacity: playable ? 1 : 0.55,
                      transform: playable ? "translateY(-4px)" : "none",
                      transition: "all 0.15s",
                    }}>
                    {String(card.value)}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}

      {phase === "done" && (
        <div style={{ textAlign: "center", padding: 32 }}>
          <div style={{ fontSize: 56 }}>{winner === "player" ? "🎉" : "🤖"}</div>
          <h2>{winner === "player" ? "You win! 🎴 UNO OUT!" : "AI wins this round."}</h2>
          <button onClick={deal} style={{ background: "#dc2626", color: "#fff", padding: "12px 28px",
            fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer", fontWeight: 700 }}>
            ▶ Play again
          </button>
        </div>
      )}
    </main>
  );
}

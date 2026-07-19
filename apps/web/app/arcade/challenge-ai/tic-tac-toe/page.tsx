"use client";

// Tic-Tac-Toe Duel vs the AI. You are X, the AI is O. On Hard the AI uses full
// minimax and is unbeatable (a perfect player can, at best, be forced to draw);
// Easy/Medium mix in random moves so beginners can win. Fully client-side.

import Link from "next/link";
import { useEffect, useState } from "react";

type Cell = "X" | "O" | "";
type Level = "easy" | "medium" | "hard";

const LINES = [
  [0, 1, 2], [3, 4, 5], [6, 7, 8],
  [0, 3, 6], [1, 4, 7], [2, 5, 8],
  [0, 4, 8], [2, 4, 6],
];

function winner(b: Cell[]): Cell | "draw" | "" {
  for (const [a, c, d] of LINES) if (b[a] && b[a] === b[c] && b[a] === b[d]) return b[a];
  return b.every((x) => x) ? "draw" : "";
}

// Minimax: score from O's (AI) perspective. +10 win, -10 loss, sooner is better.
function minimax(b: Cell[], turn: Cell): { score: number; move: number } {
  const w = winner(b);
  if (w === "O") return { score: 10, move: -1 };
  if (w === "X") return { score: -10, move: -1 };
  if (w === "draw") return { score: 0, move: -1 };
  let best = { score: turn === "O" ? -Infinity : Infinity, move: -1 };
  for (let i = 0; i < 9; i++) {
    if (b[i]) continue;
    b[i] = turn;
    const r = minimax(b, turn === "O" ? "X" : "O");
    b[i] = "";
    const score = r.score - Math.sign(r.score) * 0.1;
    if (turn === "O" ? score > best.score : score < best.score) best = { score, move: i };
  }
  return best;
}

function aiMove(b: Cell[], level: Level): number {
  const empty = b.map((c, i) => (c ? -1 : i)).filter((i) => i >= 0);
  const randPick = () => empty[Math.floor(Math.random() * empty.length)];
  const randomChance = level === "easy" ? 0.7 : level === "medium" ? 0.3 : 0;
  if (Math.random() < randomChance) return randPick();
  return minimax([...b], "O").move;
}

export default function TicTacToe() {
  const [level, setLevel] = useState<Level>("hard");
  const [board, setBoard] = useState<Cell[]>(Array(9).fill(""));
  const [turn, setTurn] = useState<Cell>("X");
  const [record, setRecord] = useState({ w: 0, l: 0, d: 0 });

  useEffect(() => {
    try {
      const r = JSON.parse(localStorage.getItem("aoep_ttt_record") || "");
      if (r && typeof r.w === "number") setRecord(r);
    } catch { /* */ }
  }, []);

  const result = winner(board);

  useEffect(() => {
    if (result === "") return;
    setRecord((r) => {
      const nr = { ...r };
      if (result === "X") nr.w += 1;
      else if (result === "O") nr.l += 1;
      else nr.d += 1;
      try { localStorage.setItem("aoep_ttt_record", JSON.stringify(nr)); } catch { /* */ }
      return nr;
    });
  }, [result]);

  // AI turn.
  useEffect(() => {
    if (turn !== "O" || result) return;
    const t = setTimeout(() => {
      const m = aiMove(board, level);
      if (m >= 0) {
        setBoard((b) => { const n = [...b]; n[m] = "O"; return n; });
        setTurn("X");
      }
    }, 420);
    return () => clearTimeout(t);
  }, [turn, board, level, result]);

  const play = (i: number) => {
    if (board[i] || result || turn !== "X") return;
    setBoard((b) => { const n = [...b]; n[i] = "X"; return n; });
    setTurn("O");
  };

  const reset = () => { setBoard(Array(9).fill("")); setTurn("X"); };

  const banner = result === "X" ? "🎉 You beat the AI!"
    : result === "O" ? "🤖 The AI wins this one."
    : result === "draw" ? "🤝 Draw — well played."
    : turn === "X" ? "Your move (X)" : "AI is thinking…";

  return (
    <main style={{ maxWidth: 520, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>❌⭕ Tic-Tac-Toe Duel</h1>
        <Link href="/arcade/challenge-ai" style={{ marginLeft: "auto" }}>← Challenge the AI</Link>
      </div>
      <p className="muted">You are X. On Hard, the AI plays perfectly — try to force a draw!</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <span className="muted">Difficulty:</span>
        {(["easy", "medium", "hard"] as Level[]).map((l) => (
          <button key={l} onClick={() => { setLevel(l); reset(); }}
            style={{ opacity: level === l ? 1 : 0.55, fontWeight: level === l ? 700 : 400 }}>
            {l}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>
          W {record.w} · L {record.l} · D {record.d}
        </span>
      </div>

      <div style={{ fontSize: 18, fontWeight: 700, margin: "6px 0 12px", minHeight: 26 }}>{banner}</div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, maxWidth: 360 }}>
        {board.map((c, i) => (
          <button key={i} onClick={() => play(i)}
            disabled={!!c || !!result || turn !== "X"}
            style={{
              aspectRatio: "1 / 1", fontSize: 44, fontWeight: 800, cursor: c || result ? "default" : "pointer",
              color: c === "X" ? "#7c3aed" : "#0ea5e9",
              background: "var(--card, #fff)", border: "2px solid var(--border, #ddd)", borderRadius: 12,
            }}>
            {c}
          </button>
        ))}
      </div>

      <div style={{ marginTop: 16 }}>
        <button onClick={reset} style={{ background: "#7c3aed", color: "#fff", padding: "10px 22px" }}>
          {result ? "▶ New game" : "↺ Restart"}
        </button>
      </div>
    </main>
  );
}

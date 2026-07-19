"use client";

// Grid Master — tic-tac-toe vs minimax AI. Before each of YOUR moves, answer a
// quick question; wrong answer skips your turn and the AI moves immediately.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Cell = "X" | "O" | null;

type Q = { prompt: string; options: string[]; answer: number };

const QUESTIONS: Record<Age, Q[]> = {
  kids: [
    { prompt: "3 + 4 = ?", options: ["6", "7", "8", "5"], answer: 1 },
    { prompt: "How many days in a week?", options: ["5", "6", "7", "8"], answer: 2 },
    { prompt: "Red + Blue = ?", options: ["Green", "Purple", "Orange", "Brown"], answer: 1 },
  ],
  tween: [
    { prompt: "12 × 5 = ?", options: ["50", "55", "60", "65"], answer: 2 },
    { prompt: "Area of square side 4?", options: ["8", "12", "16", "20"], answer: 2 },
    { prompt: "Largest ocean?", options: ["Atlantic", "Indian", "Pacific", "Arctic"], answer: 2 },
  ],
  teen: [
    { prompt: "√81 = ?", options: ["7", "8", "9", "10"], answer: 2 },
    { prompt: "Atomic number of Carbon?", options: ["4", "6", "8", "12"], answer: 1 },
    { prompt: "Slope formula?", options: ["Δy/Δx", "Δx/Δy", "y/x", "x/y"], answer: 0 },
  ],
  adult: [
    { prompt: "Integral of 2x?", options: ["x", "x²", "x²+C", "2x²"], answer: 2 },
    { prompt: "Central limit theorem applies to…", options: ["Sample means", "Single values", "Medians only", "Variances only"], answer: 0 },
    { prompt: "Time complexity of merge sort?", options: ["O(n)", "O(n log n)", "O(n²)", "O(log n)"], answer: 1 },
  ],
};

const LINES = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];

function winner(board: Cell[]): Cell {
  for (const [a, b, c] of LINES) {
    if (board[a] && board[a] === board[b] && board[a] === board[c]) return board[a];
  }
  return null;
}

function minimax(board: Cell[], ai: Cell, human: Cell, isMax: boolean): number {
  const w = winner(board);
  if (w === ai) return 1;
  if (w === human) return -1;
  if (board.every((c) => c)) return 0;
  if (isMax) {
    let best = -Infinity;
    for (let i = 0; i < 9; i++) {
      if (!board[i]) {
        board[i] = ai;
        best = Math.max(best, minimax(board, ai, human, false));
        board[i] = null;
      }
    }
    return best;
  }
  let best = Infinity;
  for (let i = 0; i < 9; i++) {
    if (!board[i]) {
      board[i] = human;
      best = Math.min(best, minimax(board, ai, human, true));
      board[i] = null;
    }
  }
  return best;
}

function aiMove(board: Cell[]): number {
  let bestScore = -Infinity, move = -1;
  for (let i = 0; i < 9; i++) {
    if (!board[i]) {
      board[i] = "O";
      const score = minimax(board, "O", "X", false);
      board[i] = null;
      if (score > bestScore) { bestScore = score; move = i; }
    }
  }
  return move;
}

export default function GridMaster() {
  const [age, setAge] = useState<Age>("teen");
  const [board, setBoard] = useState<Cell[]>(Array(9).fill(null));
  const [phase, setPhase] = useState<"idle" | "question" | "playing" | "done">("idle");
  const [question, setQuestion] = useState<Q | null>(null);
  const [pendingCell, setPendingCell] = useState<number | null>(null);
  const [result, setResult] = useState<"win" | "lose" | "draw" | null>(null);
  const [feedback, setFeedback] = useState("");
  const [stats, setStats] = useState({ wins: 0, losses: 0 });

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
    try {
      const s = localStorage.getItem("aoep_grid_stats");
      if (s) setStats(JSON.parse(s));
    } catch { /* */ }
  }, []);

  const pickQuestion = () => {
    const bank = QUESTIONS[age];
    return bank[Math.floor(Math.random() * bank.length)];
  };

  const start = () => {
    setBoard(Array(9).fill(null));
    setResult(null); setFeedback("");
    setPhase("playing");
  };

  const doAiTurn = useCallback((b: Cell[]) => {
    const w = winner(b);
    if (w || b.every((c) => c)) {
      const res = w === "X" ? "win" : w === "O" ? "lose" : "draw";
      setResult(res);
      setPhase("done");
      setStats((s) => {
        const ns = { wins: s.wins + (res === "win" ? 1 : 0), losses: s.losses + (res === "lose" ? 1 : 0) };
        try { localStorage.setItem("aoep_grid_stats", JSON.stringify(ns)); } catch { /* */ }
        return ns;
      });
      return;
    }
    const move = aiMove(b);
    if (move >= 0) {
      const nb = [...b]; nb[move] = "O";
      setBoard(nb);
      const w2 = winner(nb);
      if (w2 || nb.every((c) => c)) {
        const res = w2 === "X" ? "win" : w2 === "O" ? "lose" : "draw";
        setResult(res);
        setPhase("done");
        setStats((s) => {
          const ns = { wins: s.wins + (res === "win" ? 1 : 0), losses: s.losses + (res === "lose" ? 1 : 0) };
          try { localStorage.setItem("aoep_grid_stats", JSON.stringify(ns)); } catch { /* */ }
          return ns;
        });
      }
    }
  }, []);

  const clickCell = (idx: number) => {
    if (phase !== "playing" || board[idx]) return;
    setPendingCell(idx);
    setQuestion(pickQuestion());
    setPhase("question");
  };

  const answerQuestion = (idx: number) => {
    if (!question || pendingCell === null) return;
    const correct = idx === question.answer;
    if (correct) {
      setFeedback("Correct! Your move ✓");
      const nb = [...board]; nb[pendingCell] = "X";
      setBoard(nb);
      setPendingCell(null); setQuestion(null);
      setPhase("playing");
      setTimeout(() => doAiTurn(nb), 600);
    } else {
      setFeedback(`Wrong — AI gets a free move! Answer: ${question.options[question.answer]}`);
      setPendingCell(null); setQuestion(null);
      setPhase("playing");
      setTimeout(() => doAiTurn(board), 600);
    }
  };

  return (
    <main className="container" style={{ maxWidth: 520 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🎯 Grid Master</h1>
        <Link href="/arcade/challenge-ai" style={{ marginLeft: "auto" }}>← Challenge AI</Link>
      </div>
      <p className="muted">Tic-tac-toe vs a minimax AI. Answer a question before each move — miss it and the AI plays for free.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={phase === "playing" || phase === "question"}
            style={{ opacity: age === a ? 1 : 0.55 }}>{a}</button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>W {stats.wins} · L {stats.losses}</span>
      </div>

      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 24 }}>
          <button onClick={start} style={{ background: "#0ea5e9", color: "#fff", padding: "14px 32px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
            ▶ Challenge the AI
          </button>
        </div>
      )}

      {(phase === "playing" || phase === "question" || phase === "done") && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, maxWidth: 320, margin: "0 auto 20px" }}>
            {board.map((cell, i) => (
              <button key={i} onClick={() => clickCell(i)} disabled={!!cell || phase !== "playing"}
                style={{
                  aspectRatio: "1", fontSize: 36, fontWeight: 700,
                  background: cell === "X" ? "rgba(52,211,153,0.2)" : cell === "O" ? "rgba(248,113,113,0.2)" : "#1e293b",
                  color: cell === "X" ? "#34d399" : cell === "O" ? "#f87171" : "#64748b",
                  border: "2px solid #334155", borderRadius: 12, cursor: cell ? "default" : "pointer",
                }}>
                {cell ?? ""}
              </button>
            ))}
          </div>

          {phase === "question" && question && (
            <div className="card">
              <div className="muted" style={{ fontSize: 13 }}>Answer to place your X:</div>
              <h3>{question.prompt}</h3>
              <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
                {question.options.map((opt, i) => (
                  <button key={i} onClick={() => answerQuestion(i)} style={{ textAlign: "left", padding: "10px 14px" }}>
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {feedback && phase !== "question" && <p className="muted" style={{ textAlign: "center" }}>{feedback}</p>}

          {phase === "done" && (
            <div className="card" style={{ textAlign: "center" }}>
              <h2>{result === "win" ? "🎉 You beat the AI!" : result === "lose" ? "🤖 AI wins" : "🤝 Draw"}</h2>
              <button onClick={start} style={{ marginTop: 12, background: "#0ea5e9", color: "#fff", padding: "10px 24px", borderRadius: 8, border: 0, cursor: "pointer" }}>
                Rematch
              </button>
            </div>
          )}
        </>
      )}

      <p className="muted" style={{ marginTop: 20, fontSize: 13, textAlign: "center" }}>
        You are <strong style={{ color: "#34d399" }}>X</strong> · AI is <strong style={{ color: "#f87171" }}>O</strong>
      </p>
    </main>
  );
}
